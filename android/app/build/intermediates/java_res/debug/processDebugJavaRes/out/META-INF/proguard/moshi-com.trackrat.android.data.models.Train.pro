-if class com.trackrat.android.data.models.Train
-keepnames class com.trackrat.android.data.models.Train
-if class com.trackrat.android.data.models.Train
-keep class com.trackrat.android.data.models.TrainJsonAdapter {
    public <init>(com.squareup.moshi.Moshi);
}
-if class com.trackrat.android.data.models.Train
-keepnames class kotlin.jvm.internal.DefaultConstructorMarker
-if class com.trackrat.android.data.models.Train
-keepclassmembers class com.trackrat.android.data.models.Train {
    public synthetic <init>(java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,java.lang.String,int,kotlin.jvm.internal.DefaultConstructorMarker);
}
