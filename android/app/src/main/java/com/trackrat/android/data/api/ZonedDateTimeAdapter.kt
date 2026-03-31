package com.trackrat.android.data.api

import android.util.Log
import com.squareup.moshi.*
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException

/**
 * Moshi adapter for ZonedDateTime that handles Eastern Time zone
 * and multiple ISO8601 formats with fractional seconds
 */
class ZonedDateTimeAdapter : JsonAdapter<ZonedDateTime>() {
    
    companion object {
        private const val TAG = "ZonedDateTimeAdapter"
        
        // Eastern Time zone
        private val ET_ZONE = ZoneId.of("America/New_York")
        
        // Multiple formatters to try, in order of preference
        private val FORMATTERS = listOf(
            DateTimeFormatter.ISO_INSTANT,           // Handles 'Z' suffix (UTC)
            DateTimeFormatter.ISO_OFFSET_DATE_TIME,  // Standard with timezone
            DateTimeFormatter.ISO_LOCAL_DATE_TIME,   // Without timezone
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSSSS"),  // With microseconds
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS"),     // With milliseconds
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")          // Without fractions
        )
    }
    
    @FromJson
    override fun fromJson(reader: JsonReader): ZonedDateTime? {
        return when (reader.peek()) {
            JsonReader.Token.NULL -> {
                reader.nextNull()
            }
            JsonReader.Token.STRING -> {
                val dateString = reader.nextString()
                parseDateTime(dateString)
            }
            else -> throw JsonDataException("Expected string or null for ZonedDateTime")
        }
    }
    
    @ToJson
    override fun toJson(writer: JsonWriter, value: ZonedDateTime?) {
        if (value == null) {
            writer.nullValue()
        } else {
            // Always write in ISO format with timezone
            writer.value(value.format(DateTimeFormatter.ISO_OFFSET_DATE_TIME))
        }
    }
    
    private fun parseDateTime(dateString: String): ZonedDateTime {
        // Log the incoming datetime for debugging
        Log.d(TAG, "Parsing datetime: $dateString")
        
        // Special handling for ISO_INSTANT format (timestamps ending with 'Z')
        if (dateString.endsWith("Z")) {
            try {
                // Parse as Instant and convert to ZonedDateTime in ET
                val instant = java.time.Instant.parse(dateString)
                val result = ZonedDateTime.ofInstant(instant, ET_ZONE)
                Log.d(TAG, "Parsed UTC time to ET: $result")
                return result
            } catch (e: DateTimeParseException) {
                // Fall through to other formatters
            }
        }
        
        // Try each formatter until one works
        for (formatter in FORMATTERS) {
            try {
                val parsed = when {
                    // Check for explicit timezone offset (e.g., -05:00 or +00:00)
                    dateString.matches(".*[+-]\\d{2}:\\d{2}$".toRegex()) -> {
                        // Has timezone offset - parse directly
                        ZonedDateTime.parse(dateString, formatter)
                    }
                    // Check for 'Z' timezone indicator (already handled above but just in case)
                    dateString.endsWith("Z") -> {
                        ZonedDateTime.parse(dateString, formatter)
                    }
                    else -> {
                        // No timezone - parse as local time and localize to Eastern Time
                        // This handles DST correctly by using the ET_ZONE rules
                        val localDateTime = LocalDateTime.parse(dateString, formatter)
                        localDateTime.atZone(ET_ZONE)
                    }
                }
                
                // Always convert to Eastern Time for consistency
                val result = parsed.withZoneSameInstant(ET_ZONE)
                Log.d(TAG, "Successfully parsed to ET: $result")
                return result
            } catch (e: DateTimeParseException) {
                // Try next formatter
                continue
            }
        }
        
        // If no formatter worked, throw exception
        Log.e(TAG, "Failed to parse datetime: $dateString")
        throw JsonDataException("Unable to parse datetime: $dateString")
    }
}