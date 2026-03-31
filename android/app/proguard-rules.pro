# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.

# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
#-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile

##---------------Begin: proguard configuration common for all Android apps ----------

# Keep native methods
-keepclassmembers class * {
    native <methods>;
}

# Keep enum classes
-keepclassmembers enum * {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}

# Keep Serializable classes
-keepnames class * implements java.io.Serializable
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
    private static final java.io.ObjectStreamField[] serialPersistentFields;
    private void writeObject(java.io.ObjectOutputStream);
    private void readObject(java.io.ObjectInputStream);
    java.lang.Object writeReplace();
    java.lang.Object readResolve();
}

##---------------Begin: Kotlin specific rules ----------

# Kotlin serialization
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Kotlin Reflection
-keep class kotlin.reflect.jvm.internal.** { *; }
-keep class kotlin.Metadata { *; }

# Kotlin Coroutines
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}
-keepclassmembers class kotlinx.coroutines.** {
    volatile <fields>;
}

##---------------Begin: Retrofit and OkHttp ----------

# Retrofit does reflection on generic parameters. InnerClasses is required to use Signature and
# EnclosingMethod is required to use InnerClasses.
-keepattributes Signature, InnerClasses, EnclosingMethod

# Retrofit does reflection on method and parameter annotations.
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations

# Keep annotation default values (e.g., retrofit2.http.Field.encoded).
-keepattributes AnnotationDefault

# Retain service method parameters when optimizing.
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}

# Ignore annotation used for build tooling.
-dontwarn org.codehaus.mojo.animal_sniffer.IgnoreJRERequirement

# Ignore JSR 305 annotations for embedding nullability information.
-dontwarn javax.annotation.**

# Guarded by a NoClassDefFoundError try/catch and only used when on the classpath.
-dontwarn kotlin.Unit

# Top-level functions that can only be used by Kotlin.
-dontwarn retrofit2.KotlinExtensions

# With R8 full mode, it sees no subtypes of Retrofit interfaces since they are created with a Proxy
# and replaces all potential values with null. Explicitly keeping the interfaces prevents this.
-if interface * { @retrofit2.http.* <methods>; }
-keep,allowobfuscation interface <1>

# Keep generic signature of Call, Response (R8 full mode strips signatures from non-kept items).
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response

# With R8 full mode generic signatures are stripped for classes that are not
# kept. Suspend functions are wrapped in continuations where the type argument
# is used.
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation

# OkHttp platform used only on JVM and when Conscrypt dependency is available.
-dontwarn okhttp3.internal.platform.ConscryptPlatform
-dontwarn org.conscrypt.ConscryptHostnameVerifier

##---------------Begin: Moshi ----------

# JSR 305 annotations are for embedding nullability information.
-dontwarn javax.annotation.**

# A resource is loaded with a relative path so the package of this class must be preserved.
-keepnames class okio.Okio

# Animal Sniffer compileOnly dependency to ensure APIs are compatible with older versions of Java.
-dontwarn org.codehaus.mojo.animal_sniffer.IgnoreJRERequirement

# Moshi uses generic type information at runtime
-keepattributes Signature
-keepattributes *Annotation*

# Keep JsonAdapter classes
-keep class * extends com.squareup.moshi.JsonAdapter

# Keep all data classes used for JSON serialization
-keep @com.squareup.moshi.JsonClass class * { *; }

# Keep generated JsonAdapters
-keep class **JsonAdapter {
    <init>(...);
    <fields>;
}

# Keep constructor of classes that have @JsonClass(generateAdapter = true)
-keepclassmembers @com.squareup.moshi.JsonClass class * {
    <init>(...);
}

# Keep Kotlin metadata for Moshi reflective adapter
-keepclassmembers class kotlin.Metadata {
    public <methods>;
}

##---------------Begin: Hilt ----------

# Keep Hilt generated classes
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper { *; }

# Keep all @Module classes
-keep @dagger.Module class * { *; }
-keep @dagger.hilt.InstallIn class * { *; }

# Keep all @Component classes and their methods
-keep @dagger.Component class * { *; }
-keep @dagger.hilt.components.SingletonComponent class * { *; }

# Keep all @Inject constructors
-keepclassmembers class * {
    @javax.inject.Inject <init>(...);
}

# Keep all @Inject fields
-keepclassmembers class * {
    @javax.inject.Inject <fields>;
}

# Keep all @Inject methods
-keepclassmembers class * {
    @javax.inject.Inject <methods>;
}

# Keep ViewModel classes and their constructors (for Hilt injection)
-keep class * extends androidx.lifecycle.ViewModel {
    <init>(...);
}

# Keep @HiltViewModel classes
-keep @dagger.hilt.android.lifecycle.HiltViewModel class * { *; }

##---------------Begin: Compose ----------

# Keep Compose-related classes
-keep class androidx.compose.** { *; }

# Keep classes that use @Composable annotation
-keep @androidx.compose.runtime.Composable class * { *; }
-keepclassmembers class * {
    @androidx.compose.runtime.Composable <methods>;
}

# Keep ComposerKt for runtime
-keep class androidx.compose.runtime.ComposerKt { *; }

##---------------Begin: TrackRat-specific rules ----------

# Keep all data models (they're used by Moshi for JSON parsing)
-keep class com.trackrat.android.data.models.** { *; }

# Keep API service interfaces
-keep interface com.trackrat.android.data.api.** { *; }

# Keep custom adapters
-keep class com.trackrat.android.data.api.ZonedDateTimeAdapter { *; }

# Keep ViewModels
-keep class com.trackrat.android.ui.**.ViewModel { *; }
-keep class com.trackrat.android.ui.**.*ViewModel { *; }

# Keep Repository classes
-keep class com.trackrat.android.data.repository.** { *; }

# Keep Service classes
-keep class com.trackrat.android.services.** { *; }

##---------------Begin: Generic Android rules ----------

# Keep custom views and their constructors
-keepclassmembers public class * extends android.view.View {
    public <init>(android.content.Context);
    public <init>(android.content.Context, android.util.AttributeSet);
    public <init>(android.content.Context, android.util.AttributeSet, int);
}

# Keep activity methods that might be called from XML or intent filters
-keepclassmembers class * extends android.app.Activity {
    public void *(android.view.View);
}

##---------------Begin: Testing rules ----------

# Keep test-related classes if they exist
-keep class * extends junit.framework.TestCase
-keepclassmembers class * extends junit.framework.TestCase {
    public void test*();
}

##---------------End----------