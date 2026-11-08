// FeedLagMonitor — NinjaTrader 8 indicator (portfolio sample, no trading logic).
// Author: Sergei Rokossovskii (QuantState LLC).
//
// Problem it detects: on heavy sessions NinjaTrader may process market-data events minutes after the exchange
// timestamp (a queue builds up behind slow scripts/indicators), while Chart Trader still shows the live quote.
// Anything that trades from the delayed stream acts on a stale book.
//
// Two independent signals, either one marks the feed STALE:
//   1. lag  = (now − exchange time of the event being processed) − baseline, where the baseline (constant clock
//             offset + network) is the minimum of the last 30 one-minute minima, clamped to ±MaxBaselineSec;
//   2. div  = how far the trade being processed lies outside the CURRENT bid/ask snapshot, held ≥ 1 s.
// The state recovers only after ResumeSec of clean data (hysteresis). Market Replay is detected and ignored.
#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using System.Diagnostics;
using System.Globalization;
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
        private double _lagSec, _rawSec, _divTicks;
        private DateTime _divSince = DateTime.MinValue, _cleanSince = DateTime.MinValue, _lastEval = DateTime.MinValue;
        private bool _stale;
        private int _episodes;

        [NinjaScriptProperty, Range(0.5, 600), Display(Name = "Max lag (s)", Order = 1, GroupName = "Parameters")]
        public double MaxLagSec { get; set; }

        [NinjaScriptProperty, Range(1, 200), Display(Name = "Max divergence (ticks)", Order = 2, GroupName = "Parameters")]
        public int MaxDivTicks { get; set; }

        [NinjaScriptProperty, Range(1, 600), Display(Name = "Resume after clean (s)", Order = 3, GroupName = "Parameters")]
        public double ResumeSec { get; set; }

        [NinjaScriptProperty, Range(1, 3600), Display(Name = "Max baseline (s)", Order = 4, GroupName = "Parameters")]
        public double MaxBaselineSec { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "FeedLagMonitor";
                Description = "Detects a delayed market-data stream (event time vs clock, trade vs live quote).";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                MaxLagSec = 3; MaxDivTicks = 8; ResumeSec = 30; MaxBaselineSec = 300;
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
            DateTime nowUtc = DateTime.UtcNow;
            DateTime ntNowUtc = NtToUtc(NinjaTrader.Core.Globals.Now);
            if (Math.Abs((ntNowUtc - nowUtc).TotalMinutes) > 5) return;      // Market Replay / Playback

            DateTime evUtc = NtToUtc(e.Time);
            _rawSec = (nowUtc - evUtc).TotalSeconds;
            long key = nowUtc.Ticks / TimeSpan.TicksPerMinute;
            int s = (int)(key % Slots);
            if (_slotKey[s] != key) { _slotKey[s] = key; _minRaw[s] = _rawSec; }
            else if (_rawSec < _minRaw[s]) _minRaw[s] = _rawSec;
            _lagSec = _rawSec - Baseline(key);

            if (e.MarketDataType == MarketDataType.Last && TickSize > 0)
            {
                double bid = GetCurrentBid(), ask = GetCurrentAsk();
                _divTicks = (bid > 0 && ask >= bid) ? Math.Max(0, Math.Max(bid - e.Price, e.Price - ask)) / TickSize : 0;
                if (_divTicks > MaxDivTicks) { if (_divSince == DateTime.MinValue) _divSince = nowUtc; }
                else _divSince = DateTime.MinValue;
            }
            if (_lastEval != DateTime.MinValue && (nowUtc - _lastEval).TotalMilliseconds < 250) return;
            _lastEval = nowUtc;
            Evaluate(nowUtc);
        }

        private double Baseline(long nowKey)
        {
            double best = double.NaN;
            for (int i = 0; i < Slots; i++)
                if (_slotKey[i] != 0 && nowKey - _slotKey[i] < Slots && (double.IsNaN(best) || _minRaw[i] < best)) best = _minRaw[i];
            return double.IsNaN(best) ? 0 : Math.Max(-MaxBaselineSec, Math.Min(MaxBaselineSec, best));
        }

        private void Evaluate(DateTime now)
        {
            bool bad = _lagSec > MaxLagSec || _rawSec > MaxBaselineSec
                       || (_divSince != DateTime.MinValue && (now - _divSince).TotalSeconds >= 1.0);
            if (bad)
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

        private string Line(string st) => string.Format(CultureInfo.InvariantCulture,
            "[FEED-LAG] {0} {1} lag={2:F1}s raw={3:F1}s div={4:F0}t episodes={5}", Instrument?.FullName, st, _lagSec, _rawSec, _divTicks, _episodes);
    }
}
