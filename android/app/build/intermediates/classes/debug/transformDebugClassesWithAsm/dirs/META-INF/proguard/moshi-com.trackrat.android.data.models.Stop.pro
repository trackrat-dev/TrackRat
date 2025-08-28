-if class com.trackrat.android.data.models.Stop
-keepnames class com.trackrat.android.data.models.Stop
-if class com.trackrat.android.data.models.Stop
-keep class com.trackrat.android.data.models.StopJsonAdapter {
    public <init>(com.squareup.moshi.Moshi);
}
-if class com.trackrat.android.data.models.Stop
-keepnames class kotlin.jvm.internal.DefaultConstructorMarker
-if class com.trackrat.android.data.models.Stop
-keepclassmembers class com.trackrat.android.data.models.Stop {
    public synthetic <init>(java.lang.String,java.lang.String,int,java.time.ZonedDateTime,java.time.ZonedDateTime,java.time.ZonedDateTime,java.time.ZonedDateTime,boolean,java.lang.String,java.lang.String,java.lang.String,int,kotlin.jvm.internal.DefaultConstructorMarker);
}
