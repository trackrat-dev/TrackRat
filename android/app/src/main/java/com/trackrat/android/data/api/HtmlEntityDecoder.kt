package com.trackrat.android.data.api

import android.text.Html
import android.os.Build
import com.squareup.moshi.JsonAdapter
import com.squareup.moshi.JsonQualifier
import com.squareup.moshi.JsonReader
import com.squareup.moshi.JsonWriter
import com.squareup.moshi.Moshi
import java.lang.reflect.Type

/**
 * Annotation to mark String fields that should have HTML entities decoded
 */
@Retention(AnnotationRetention.RUNTIME)
@Target(AnnotationTarget.FIELD, AnnotationTarget.PROPERTY, AnnotationTarget.VALUE_PARAMETER)
@JsonQualifier
annotation class HtmlDecode

/**
 * JsonAdapter that decodes HTML entities in String values
 * Handles entities like &#9992; (airplane emoji) that may appear in API responses
 */
class HtmlEntityDecodeJsonAdapter : JsonAdapter<String>() {
    
    override fun fromJson(reader: JsonReader): String? {
        val value = reader.nextString()
        return value?.let { decodeHtmlEntities(it) }
    }

    override fun toJson(writer: JsonWriter, value: String?) {
        writer.value(value)
    }

    companion object {
        /**
         * Decodes HTML entities in a string using Android's Html class
         */
        fun decodeHtmlEntities(input: String): String {
            return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                Html.fromHtml(input, Html.FROM_HTML_MODE_LEGACY).toString()
            } else {
                @Suppress("DEPRECATION")
                Html.fromHtml(input).toString()
            }
        }
    }
}

/**
 * Factory for creating HtmlEntityDecodeJsonAdapter instances
 */
class HtmlEntityDecodeJsonAdapterFactory : JsonAdapter.Factory {
    override fun create(
        type: Type,
        annotations: Set<Annotation>,
        moshi: Moshi
    ): JsonAdapter<*>? {
        // Only handle String types with @HtmlDecode annotation
        if (type != String::class.java) {
            return null
        }
        
        annotations.forEach { annotation ->
            if (annotation is HtmlDecode) {
                return HtmlEntityDecodeJsonAdapter()
            }
        }
        
        return null
    }
}

/**
 * Alternative: A generic String adapter that always decodes HTML entities
 * Use this if we want to decode ALL strings from the API
 */
class UniversalHtmlDecodeAdapter : JsonAdapter<String>() {
    
    override fun fromJson(reader: JsonReader): String? {
        val value = reader.nextString()
        return value?.let { HtmlEntityDecodeJsonAdapter.decodeHtmlEntities(it) }
    }

    override fun toJson(writer: JsonWriter, value: String?) {
        writer.value(value)
    }
}