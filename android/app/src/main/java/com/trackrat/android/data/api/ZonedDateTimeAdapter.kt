package com.trackrat.android.data.api

import com.squareup.moshi.*
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
        // Special handling for ISO_INSTANT format (timestamps ending with 'Z')
        if (dateString.endsWith("Z")) {
            try {
                // Parse as Instant and convert to ZonedDateTime in ET
                val instant = java.time.Instant.parse(dateString)
                return ZonedDateTime.ofInstant(instant, ET_ZONE)
            } catch (e: DateTimeParseException) {
                // Fall through to other formatters
            }
        }
        
        // Try each formatter until one works
        for (formatter in FORMATTERS) {
            try {
                val parsed = if (dateString.contains("[zZ+-]".toRegex())) {
                    // Has timezone info - parse directly
                    ZonedDateTime.parse(dateString, formatter)
                } else {
                    // No timezone - assume Eastern Time
                    ZonedDateTime.parse(dateString + "-05:00", formatter).withZoneSameLocal(ET_ZONE)
                }
                
                // Always convert to Eastern Time for consistency
                return parsed.withZoneSameInstant(ET_ZONE)
            } catch (e: DateTimeParseException) {
                // Try next formatter
                continue
            }
        }
        
        // If no formatter worked, throw exception
        throw JsonDataException("Unable to parse datetime: $dateString")
    }
}