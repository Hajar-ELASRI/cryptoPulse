package com.cryptopulse.api;
import org.junit.jupiter.api.Test;
import org.bson.Document;
import java.time.Instant;
import java.util.Date;
import static org.assertj.core.api.Assertions.assertThat;
class MarketRepositoryTest {
    @Test void liveUsesExplicitModeAndRunInsteadOfMissingSession() {
        var f=MarketFilter.parse("BTCUSDT",null,null,2,25,null,null,null,null,false);
        var q=MarketRepository.query("indicators","window_start",f);
        assertThat(q.getQueryObject().getList("$and",Document.class)).containsExactly(
            new Document("run_id","live"),new Document("mode","live"),new Document("symbol","BTCUSDT"));
        assertThat(q.getSkip()).isEqualTo(50);
        assertThat(q.getLimit()).isEqualTo(25);
        assertThat(q.getSortObject()).isEqualTo(new Document("window_start",-1).append("_id",-1));
    }
    @Test void replayUsesAscendingTimeBoundsBeforePagination() {
        var f=MarketFilter.parse("BTCUSDT","2026-10-16T09:00:00Z","2026-10-16T10:00:00Z",1,10,
            null,null,null,"replay-demo",true);
        var q=MarketRepository.query("indicators","window_start",f);
        assertThat(q.getQueryObject().getList("$and",Document.class)).contains(
            new Document("run_id","replay-demo"),new Document("mode","replay"),
            new Document("window_start",new Document("$gte",Date.from(Instant.parse("2026-10-16T09:00:00Z")))
                .append("$lt",Date.from(Instant.parse("2026-10-16T10:00:00Z")))));
        assertThat(q.getSortObject()).isEqualTo(new Document("window_start",1).append("_id",1));
        assertThat(q.getSkip()).isEqualTo(10);
    }
    @Test void sentimentDoesNotApplyGoldPartitionAndMatchesTradeSymbolsAndLabel() {
        var f=MarketFilter.parse("BTCUSDT",null,null,0,50,null,null,"positive",null,false);
        assertThat(MarketRepository.query("sentiment","event_time",f).getQueryObject().getList("$and",Document.class))
            .containsExactly(new Document("trade_symbols","BTCUSDT"),new Document("label","positive"));
    }
    @Test void alertTypeAndSeverityReachMongo() {
        var f=MarketFilter.parse(null,null,null,0,100,"PRICE_MOVE","critical",null,null,false);
        assertThat(MarketRepository.query("alerts","event_time",f).getQueryObject().getList("$and",Document.class))
            .contains(new Document("type","PRICE_MOVE"),new Document("severity","critical"));
    }
}

