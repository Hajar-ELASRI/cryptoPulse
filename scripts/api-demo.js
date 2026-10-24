// Synthetic, idempotent fixtures; never writes the production ingestion database.
const demo = db.getSiblingDB("crypto_pulse_demo");
const start = ISODate("2026-10-16T09:00:00Z");
const end = ISODate("2026-10-16T09:01:00Z");
const stored = ISODate("2026-10-16T09:02:00Z");
for (const run of ["live", "replay-btc-demo"]) {
  const mode = run === "live" ? "live" : "replay";
  for (const [symbol, price, volume] of [["BTCUSDT","67000.10","83750.125"], ["ETHUSDT","2600.25","3250.3125"]]) {
    const id = run + ":" + symbol + ":2026-10-16T09:00:00Z";
    demo.indicators.replaceOne({_id:id}, {
      _id:id, run_id:run, mode, symbol, window_start:start, window_end:end, trade_count:10,
      base_volume:NumberDecimal("1.25"), quote_volume:NumberDecimal(volume),
      min_price:NumberDecimal(price), max_price:NumberDecimal(price), avg_price:NumberDecimal(price),
      open_price:NumberDecimal(price), close_price:NumberDecimal(price),
      change_pct:null, prev_window_start:null, updated_at:stored
    }, {upsert:true});
  }
  const id = run + ":VOLUME_SPIKE:BTCUSDT:2026-10-16T09:00:00Z";
  demo.alerts.replaceOne({_id:id}, {
    _id:id, run_id:run, mode, symbol:"BTCUSDT", type:"VOLUME_SPIKE", severity:"warning",
    event_time:end, window_start:start, observed_value:2.5, threshold:2.0, baseline:33500.05, unit:"ratio",
    reason:"Synthetic demo: volume 83750.125 USDT is 2.5 times the previous 20-window mean of 33500.05 USDT.",
    ref_event_id:null, created_at:stored
  }, {upsert:true});
}
demo.sentiment.replaceOne({_id:"sentiment:rss:demo"}, {
  _id:"sentiment:rss:demo", event_id:"sentiment:rss:demo", source_event_id:"rss:demo",
  source_topic:"crypto-news", source:"rss", symbols:["BTC"], trade_symbols:["BTCUSDT"],
  label:"positive", score:0.64, model:"vader", event_time:start, processed_at:end, stored_at:stored
}, {upsert:true});
demo.indicators.createIndex({mode:1,run_id:1,symbol:1,window_start:-1,_id:-1});
demo.alerts.createIndex({mode:1,run_id:1,symbol:1,event_time:-1,_id:-1});
demo.sentiment.createIndex({trade_symbols:1,event_time:-1,_id:-1});
print("API fixtures ready in crypto_pulse_demo; live and replay-btc-demo.");

