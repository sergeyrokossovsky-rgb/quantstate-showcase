// FeedLagMonitor — NinjaTrader 8 indicator (portfolio sample, no trading logic).
// Author: Sergei Rokossovskii (QuantState LLC).
//
// Problem it detects: on heavy sessions NinjaTrader may process market-data events minutes after the exchange
// timestamp (a queue builds up behind slow scripts/indicators), while Chart Trader still shows the live quote.
// Anything that trades from the delayed stream acts on a stale book.
//
// Two independent signals, either one marks the feed STALE:
//   1. lag  = (now − exchange time of the TRADE being processed) − baseline. Baseline (constant clock offset +
//             network) = lowest one-minute minimum of the last 30 minutes, ignoring minutes that sit more than
//             5 s below the median minute, never below 0 and never above MaxBaselineSec.
//             Must exceed MaxLagSec on ≥ 2 consecutive trades and for ≥ HoldSec.
//   2. div  = how far the trade being processed lies outside the CURRENT bid/ask snapshot, held ≥ DivHoldSec.
// The state recovers only after ResumeSec of clean data (hysteresis). Market Replay is detected and ignored.
//
// v2 (field lessons): only trades are measured — some non-trade events carry a local-clock stamp, and one such
// stamp used to pull the minimum-based baseline 18 s below zero, turning every normal event into a "3 s lag".
// Also logs the longest pause between events (a stalled instrument thread shows up as a long gap) and, optionally,
// a CSV row every 10 s so several instruments can be compared: if all of them fall behind at the same moment the
// cause is upstream (network / data feed / whole PC); if only one does, it is that instrument's processing.
#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using NinjaTrader.Data;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class FeedLagMonitor : Indicator
    {
        private const int Slots = 30;
        private readonly double[] _minRaw = new double[Slots];
        private readonly long[] _slotKey = new long[Slots];
        private double _lagSec, _rawSec = double.NaN, _divTicks, _lagMax10, _gapMaxMs;
        private DateTime _divSince = DateTime.MinValue, _lagSince = DateTime.MinValue, _cleanSince = DateTime.MinValue;
        private DateTime _lastEval = DateTime.MinValue, _csvWindow = DateTime.MinValue;
        private int _lateTrades, _episodes, _trades10;
        private long _lastEventTs;
        private bool _stale;
        private string _csvPath;

        [NinjaScriptProperty, Range(0.5, 600), Display(Name = "Max lag (s)", Order = 1, GroupName = "Parameters")]
        public double MaxLagSec { get; set; }

        [NinjaScriptProperty, Range(0, 60), Display(Name = "Hold lag (s)", Order = 2, GroupName = "Parameters")]
        public double HoldSec { get; set; }

        [NinjaScriptProperty, Range(1, 200), Display(Name = "Max divergence (ticks)", Order = 3, GroupName = "Parameters")]
        public int MaxDivTicks { get; set; }

        [NinjaScriptProperty, Range(0, 60), Display(Name = "Hold divergence (s)", Order = 4, GroupName = "Parameters")]
        public double DivHoldSec { get; set; }

        [NinjaScriptProperty, Range(1, 600), Display(Name = "Resume after clean (s)", Order = 5, GroupName = "Parameters")]
        public double ResumeSec { get; set; }

        [NinjaScriptProperty, Range(1, 3600), Display(Name = "Max baseline (s)", Order = 6, GroupName = "Parameters")]
        public double MaxBaselineSec { get; set; }

        [NinjaScriptProperty, Display(Name = "CSV every 10 s", Order = 7, GroupName = "Parameters")]
        public bool WriteCsv { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "FeedLagMonitor";
                Description = "Detects a delayed market-data stream (trade time vs clock, trade vs live quote).";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                IsSuspendedWhileInactive = false;
                MaxLagSec = 5; HoldSec = 3; MaxDivTicks = 8; DivHoldSec = 2; ResumeSec = 30; MaxBaselineSec = 300; WriteCsv = false;
            }
            else if (State == State.DataLoaded && WriteCsv)
            {
                string dir = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "FeedLag");
                Directory.CreateDirectory(dir);
                _csvPath = Path.Combine(dir, "feedlag_" + Instrument.MasterInstrument.Name + "_" + DateTime.UtcNow.ToString("yyyyMMdd") + ".csv");
                if (!File.Exists(_csvPath)) File.AppendAllText(_csvPath, "utc,symbol,trades,lag_s,lag_max_s,raw_s,div_t,gap_max_ms\r\n");
            }
        }

        // drawing stays on the bar thread; OnMarketData only updates the state
        protected override void OnBarUpdate()
        {
            if (State == State.Realtime)
                Draw.TextFixed(this, "feedlag", Line(_stale ? "STALE" : "OK"), TextPosition.TopRight);
        }

        private static DateTime NtToUtc(DateTime t) =>
            TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(t, DateTimeKind.Unspecified),
                NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);

        protected override void OnMarketData(MarketDataEventArgs e)
        {
            if (State != State.Realtime || e == null) return;
            long ts = Stopwatch.GetTimestamp();
            if (_lastEventTs != 0) _gapMaxMs = Math.Max(_gapMaxMs, (ts - _lastEventTs) * 1000.0 / Stopwatch.Frequency);
            _lastEventTs = ts;
            DateTime nowUtc = DateTime.UtcNow;
            if (Math.Abs((NtToUtc(NinjaTrader.Core.Globals.Now) - nowUtc).TotalMinutes) > 5) return;   // Market Replay

            if (e.MarketDataType == MarketDataType.Last && e.Price > 0)
            {
                _trades10++;
                _rawSec = (nowUtc - NtToUtc(e.Time)).TotalSeconds;
                long key = nowUtc.Ticks / TimeSpan.TicksPerMinute;
                int s = (int)(key % Slots);
                if (_slotKey[s] != key) { _slotKey[s] = key; _minRaw[s] = _rawSec; }
                else if (_rawSec < _minRaw[s]) _minRaw[s] = _rawSec;
                _lagSec = _rawSec - Baseline(key);
                _lagMax10 = Math.Max(_lagMax10, _lagSec);
                _lateTrades = (_lagSec > MaxLagSec || _rawSec > MaxBaselineSec) ? _lateTrades + 1 : 0;

                double bid = GetCurrentBid(), ask = GetCurrentAsk();
                _divTicks = (bid > 0 && ask >= bid && TickSize > 0) ? Math.Max(0, Math.Max(bid - e.Price, e.Price - ask)) / TickSize : 0;
                if (_divTicks > MaxDivTicks) { if (_divSince == DateTime.MinValue) _divSince = nowUtc; }
                else _divSince = DateTime.MinValue;
            }
            if (double.IsNaN(_rawSec)) return;
            if (_csvPath != null && (nowUtc - _csvWindow).TotalSeconds >= 10) WriteRow(nowUtc);
            if (_lastEval != DateTime.MinValue && (nowUtc - _lastEval).TotalMilliseconds < 250) return;
            _lastEval = nowUtc;
            Evaluate(nowUtc);
        }

        /// <summary>Lowest per-minute minimum of the last 30 min; outlier minutes (5 s below the median) are skipped.</summary>
        private double Baseline(long nowKey)
        {
            double[] v = new double[Slots];
            int n = 0;
            for (int i = 0; i < Slots; i++)
                if (_slotKey[i] != 0 && nowKey - _slotKey[i] < Slots) v[n++] = _minRaw[i];
            if (n == 0) return 0;
            Array.Sort(v, 0, n);
            double med = v[n / 2], best = med;
            for (int i = 0; i < n; i++) if (v[i] >= med - 5.0) { best = v[i]; break; }
            return Math.Max(0, Math.Min(MaxBaselineSec, best));   // a clock that is behind can hide lag, never invent it
        }

        private void Evaluate(DateTime now)
        {
            if (_lateTrades > 0) { if (_lagSince == DateTime.MinValue) _lagSince = now; } else _lagSince = DateTime.MinValue;
            bool lagBad = _lateTrades >= 2 && (now - _lagSince).TotalSeconds >= HoldSec;
            bool divBad = _divSince != DateTime.MinValue && (now - _divSince).TotalSeconds >= DivHoldSec;
            if (lagBad || divBad)
            {
                _cleanSince = DateTime.MinValue;
                if (!_stale) { _stale = true; _episodes++; Print(Line("STALE")); }
            }
            else if (_stale)
            {
                if (_cleanSince == DateTime.MinValue) _cleanSince = now;
                else if ((now - _cleanSince).TotalSeconds >= ResumeSec) { _stale = false; Print(Line("OK")); }
            }
        }

        private void WriteRow(DateTime now)
        {
            try
            {
                File.AppendAllText(_csvPath, string.Format(CultureInfo.InvariantCulture, "{0:yyyy-MM-ddTHH:mm:ss}Z,{1},{2},{3:F2},{4:F2},{5:F2},{6:F0},{7:F0}\r\n",
                    now, Instrument.MasterInstrument.Name, _trades10, _lagSec, _lagMax10, _rawSec, _divTicks, _gapMaxMs));
            }
            catch { }
            _csvWindow = now; _trades10 = 0; _lagMax10 = 0; _gapMaxMs = 0;
        }

        private string Line(string st) => string.Format(CultureInfo.InvariantCulture,
            "[FEED-LAG] {0} {1} lag={2:F1}s raw={3:F1}s div={4:F0}t episodes={5}", Instrument?.FullName, st, _lagSec, _rawSec, _divTicks, _episodes);
    }
}
