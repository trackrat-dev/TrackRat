package com.trackrat.android.data.models;

import com.squareup.moshi.Json;
import com.squareup.moshi.JsonClass;

/**
 * Owl system track prediction with confidence levels
 */
@com.squareup.moshi.JsonClass(generateAdapter = true)
@kotlin.Metadata(mv = {1, 9, 0}, k = 1, xi = 48, d1 = {"\u0000<\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u0007\n\u0000\n\u0002\u0010 \n\u0000\n\u0002\u0010$\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0010\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001BA\u0012\n\b\u0001\u0010\u0002\u001a\u0004\u0018\u00010\u0003\u0012\b\b\u0001\u0010\u0004\u001a\u00020\u0005\u0012\u000e\b\u0001\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00030\u0007\u0012\u0014\b\u0001\u0010\b\u001a\u000e\u0012\u0004\u0012\u00020\u0003\u0012\u0004\u0012\u00020\u00050\t\u00a2\u0006\u0002\u0010\nJ\u000b\u0010\u0019\u001a\u0004\u0018\u00010\u0003H\u00c6\u0003J\t\u0010\u001a\u001a\u00020\u0005H\u00c6\u0003J\u000f\u0010\u001b\u001a\b\u0012\u0004\u0012\u00020\u00030\u0007H\u00c6\u0003J\u0015\u0010\u001c\u001a\u000e\u0012\u0004\u0012\u00020\u0003\u0012\u0004\u0012\u00020\u00050\tH\u00c6\u0003JE\u0010\u001d\u001a\u00020\u00002\n\b\u0003\u0010\u0002\u001a\u0004\u0018\u00010\u00032\b\b\u0003\u0010\u0004\u001a\u00020\u00052\u000e\b\u0003\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00030\u00072\u0014\b\u0003\u0010\b\u001a\u000e\u0012\u0004\u0012\u00020\u0003\u0012\u0004\u0012\u00020\u00050\tH\u00c6\u0001J\u0013\u0010\u001e\u001a\u00020\u001f2\b\u0010 \u001a\u0004\u0018\u00010\u0001H\u00d6\u0003J\t\u0010!\u001a\u00020\"H\u00d6\u0001J\t\u0010#\u001a\u00020\u0003H\u00d6\u0001R\u0011\u0010\u0004\u001a\u00020\u0005\u00a2\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\fR\u0011\u0010\r\u001a\u00020\u000e8F\u00a2\u0006\u0006\u001a\u0004\b\u000f\u0010\u0010R\u0011\u0010\u0011\u001a\u00020\u00038F\u00a2\u0006\u0006\u001a\u0004\b\u0012\u0010\u0013R\u001d\u0010\b\u001a\u000e\u0012\u0004\u0012\u00020\u0003\u0012\u0004\u0012\u00020\u00050\t\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u0015R\u0013\u0010\u0002\u001a\u0004\u0018\u00010\u0003\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0016\u0010\u0013R\u0017\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00030\u0007\u00a2\u0006\b\n\u0000\u001a\u0004\b\u0017\u0010\u0018\u00a8\u0006$"}, d2 = {"Lcom/trackrat/android/data/models/PredictionData;", "", "primaryPrediction", "", "confidence", "", "top3", "", "platformProbabilities", "", "(Ljava/lang/String;FLjava/util/List;Ljava/util/Map;)V", "getConfidence", "()F", "confidenceLevel", "Lcom/trackrat/android/data/models/ConfidenceLevel;", "getConfidenceLevel", "()Lcom/trackrat/android/data/models/ConfidenceLevel;", "confidenceText", "getConfidenceText", "()Ljava/lang/String;", "getPlatformProbabilities", "()Ljava/util/Map;", "getPrimaryPrediction", "getTop3", "()Ljava/util/List;", "component1", "component2", "component3", "component4", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"})
public final class PredictionData {
    @org.jetbrains.annotations.Nullable()
    private final java.lang.String primaryPrediction = null;
    private final float confidence = 0.0F;
    @org.jetbrains.annotations.NotNull()
    private final java.util.List<java.lang.String> top3 = null;
    @org.jetbrains.annotations.NotNull()
    private final java.util.Map<java.lang.String, java.lang.Float> platformProbabilities = null;
    
    public PredictionData(@com.squareup.moshi.Json(name = "primary_prediction")
    @org.jetbrains.annotations.Nullable()
    java.lang.String primaryPrediction, @com.squareup.moshi.Json(name = "confidence")
    float confidence, @com.squareup.moshi.Json(name = "top_3")
    @org.jetbrains.annotations.NotNull()
    java.util.List<java.lang.String> top3, @com.squareup.moshi.Json(name = "platform_probabilities")
    @org.jetbrains.annotations.NotNull()
    java.util.Map<java.lang.String, java.lang.Float> platformProbabilities) {
        super();
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String getPrimaryPrediction() {
        return null;
    }
    
    public final float getConfidence() {
        return 0.0F;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.util.List<java.lang.String> getTop3() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.util.Map<java.lang.String, java.lang.Float> getPlatformProbabilities() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.ConfidenceLevel getConfidenceLevel() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.lang.String getConfidenceText() {
        return null;
    }
    
    @org.jetbrains.annotations.Nullable()
    public final java.lang.String component1() {
        return null;
    }
    
    public final float component2() {
        return 0.0F;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.util.List<java.lang.String> component3() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final java.util.Map<java.lang.String, java.lang.Float> component4() {
        return null;
    }
    
    @org.jetbrains.annotations.NotNull()
    public final com.trackrat.android.data.models.PredictionData copy(@com.squareup.moshi.Json(name = "primary_prediction")
    @org.jetbrains.annotations.Nullable()
    java.lang.String primaryPrediction, @com.squareup.moshi.Json(name = "confidence")
    float confidence, @com.squareup.moshi.Json(name = "top_3")
    @org.jetbrains.annotations.NotNull()
    java.util.List<java.lang.String> top3, @com.squareup.moshi.Json(name = "platform_probabilities")
    @org.jetbrains.annotations.NotNull()
    java.util.Map<java.lang.String, java.lang.Float> platformProbabilities) {
        return null;
    }
    
    @java.lang.Override()
    public boolean equals(@org.jetbrains.annotations.Nullable()
    java.lang.Object other) {
        return false;
    }
    
    @java.lang.Override()
    public int hashCode() {
        return 0;
    }
    
    @java.lang.Override()
    @org.jetbrains.annotations.NotNull()
    public java.lang.String toString() {
        return null;
    }
}