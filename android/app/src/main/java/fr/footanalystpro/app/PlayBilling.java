package fr.footanalystpro.app;

import android.app.Activity;
import android.webkit.WebView;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import com.android.billingclient.api.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Collections;
import java.util.List;

/** Origin-scoped messages: no JavaScriptInterface exposed to arbitrary iframes. */
final class PlayBilling {
    private static final String PRODUCT = "foot_analyst_pro_premium_monthly";
    private static final String ORIGIN = "https://foot-analyst-pro.onrender.com";
    private final Activity activity;
    private final BillingClient client;
    private JavaScriptReplyProxy reply;
    private String account = "";
    private boolean connecting = false;

    PlayBilling(Activity activity, WebView web) {
        this.activity = activity;
        client = BillingClient.newBuilder(activity)
            .setListener((result, purchases) -> {
                if (result.getResponseCode() == BillingClient.BillingResponseCode.OK && purchases != null) purchases(purchases);
                else if (result.getResponseCode() == BillingClient.BillingResponseCode.USER_CANCELED) send("cancelled", "Achat annulé.");
                else if (result.getResponseCode() == BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED) restore();
                else send("error", "Google Play n’a pas confirmé l’achat. Réessaie la restauration.");
            })
            .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
            .enableAutoServiceReconnection().build();
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(web, "FootPlay", Collections.singleton(ORIGIN),
                (view, message, source, mainFrame, proxy) -> {
                    if (!mainFrame || !ORIGIN.equals(source.toString())) return;
                    reply = proxy;
                    try {
                        JSONObject data = new JSONObject(message.getData());
                        String id = data.optString("account_id");
                        if (!id.matches("[a-f0-9]{64}")) { send("error", "Connecte-toi à ton compte."); return; }
                        account = id;
                        String action = data.optString("action");
                        if (!action.equals("catalog") && !action.equals("buy") && !action.equals("restore")) return;
                        connected(() -> { if (action.equals("restore")) restore(); else catalog(action.equals("buy")); });
                    } catch (Exception ignored) { send("error", "Demande de paiement invalide."); }
                });
        }
    }
    private void connected(Runnable action) {
        if (client.isReady()) { action.run(); return; }
        if (connecting) { send("error", "Connexion Google Play en cours. Réessaie dans un instant."); return; }
        connecting = true;
        client.startConnection(new BillingClientStateListener() {
            @Override public void onBillingSetupFinished(BillingResult result) {
                connecting = false;
                if (result.getResponseCode() == BillingClient.BillingResponseCode.OK) action.run();
                else send("error", "Google Play indisponible. Installe la version provenant du Play Store.");
            }
            @Override public void onBillingServiceDisconnected() { connecting = false; }
        });
    }
    private void catalog(boolean buy) {
        QueryProductDetailsParams.Product product = QueryProductDetailsParams.Product.newBuilder()
            .setProductId(PRODUCT).setProductType(BillingClient.ProductType.SUBS).build();
        client.queryProductDetailsAsync(QueryProductDetailsParams.newBuilder().setProductList(Collections.singletonList(product)).build(),
            (result, details) -> {
                if (result.getResponseCode() != BillingClient.BillingResponseCode.OK) { send("error", "Offre Google Play indisponible."); return; }
                for (ProductDetails item : details.getProductDetailsList()) {
                    if (item.getSubscriptionOfferDetails() == null) continue;
                    for (ProductDetails.SubscriptionOfferDetails offer : item.getSubscriptionOfferDetails()) {
                        if (!"monthly".equals(offer.getBasePlanId()) || offer.getOfferId() != null) continue;
                        List<ProductDetails.PricingPhase> phases = offer.getPricingPhases().getPricingPhaseList();
                        if (phases.size() != 1 || !"P1M".equals(phases.get(0).getBillingPeriod()) || phases.get(0).getRecurrenceMode() != ProductDetails.RecurrenceMode.INFINITE_RECURRING) continue;
                        if (buy) {
                            BillingFlowParams.ProductDetailsParams params = BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(item).setOfferToken(offer.getOfferToken()).build();
                            BillingResult launched = client.launchBillingFlow(activity, BillingFlowParams.newBuilder()
                                .setProductDetailsParamsList(Collections.singletonList(params)).setObfuscatedAccountId(account).build());
                            if (launched.getResponseCode() != BillingClient.BillingResponseCode.OK) send("error", "Impossible d’ouvrir le paiement Google Play.");
                        } else {
                            JSONObject data = new JSONObject();
                            try { data.put("type", "catalog"); data.put("price", phases.get(0).getFormattedPrice()); } catch (Exception ignored) { }
                            emit(data);
                        }
                        return;
                    }
                }
                send("error", "L’abonnement mensuel n’est pas encore disponible sur Google Play.");
            });
    }
    private void restore() {
        client.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.SUBS).build(),
            (result, purchases) -> {
                if (result.getResponseCode() == BillingClient.BillingResponseCode.OK) purchases(purchases);
                else send("error", "Restauration indisponible. Réessaie dans un instant.");
            });
    }
    private void purchases(List<Purchase> purchases) {
        JSONArray tokens = new JSONArray(); boolean pending = false;
        for (Purchase purchase : purchases) {
            if (!purchase.getProducts().contains(PRODUCT)) continue;
            if (purchase.getPurchaseState() == Purchase.PurchaseState.PURCHASED) tokens.put(purchase.getPurchaseToken());
            else if (purchase.getPurchaseState() == Purchase.PurchaseState.PENDING) pending = true;
        }
        JSONObject data = new JSONObject();
        try { data.put("type", "purchases"); data.put("tokens", tokens); data.put("pending", pending); } catch (Exception ignored) { }
        emit(data);
    }
    private void send(String type, String message) {
        JSONObject data = new JSONObject();
        try { data.put("type", type); data.put("message", message); } catch (Exception ignored) { }
        emit(data);
    }
    private void emit(JSONObject data) {
        activity.runOnUiThread(() -> { if (reply != null) reply.postMessage(data.toString()); });
    }
    void close() { client.endConnection(); reply = null; }
}
