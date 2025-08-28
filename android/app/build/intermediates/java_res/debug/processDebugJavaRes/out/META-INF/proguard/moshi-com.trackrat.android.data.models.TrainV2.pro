-if class com.trackrat.android.data.models.TrainV2
-keepnames class com.trackrat.android.data.models.TrainV2
-if class com.trackrat.android.data.models.TrainV2
-keep class com.trackrat.android.data.models.TrainV2JsonAdapter {
    public <init>(com.squareup.moshi.Moshi);
}
-if class com.trackrat.android.data.models.TrainV2
-keepnames class kotlin.jvm.internal.DefaultConstructorMarker
-if class com.trackrat.android.data.models.TrainV2
-keepclassmembers class com.trackrat.android.data.models.TrainV2 {
    public synthetic <init>(java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.time.ZonedDateTime,java.time.ZonedDateTime,java.lang.String,com.trackrat.android.data.models.StatusV2,com.trackrat.android.data.models.Progress,java.lang.String,boolean,java.util.List,java.lang.String,boolean,boolean,com.trackrat.android.data.models.PredictionData,int,kotlin.jvm.internal.DefaultConstructorMarker);
}
