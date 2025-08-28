-if class com.trackrat.android.data.models.PredictionData
-keepnames class com.trackrat.android.data.models.PredictionData
-if class com.trackrat.android.data.models.PredictionData
-keep class com.trackrat.android.data.models.PredictionDataJsonAdapter {
    public <init>(com.squareup.moshi.Moshi);
}
