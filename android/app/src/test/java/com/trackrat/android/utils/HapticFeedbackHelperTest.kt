package com.trackrat.android.utils

import android.content.Context
import android.os.Vibrator
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import kotlinx.coroutines.runBlocking
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.Mock
import org.mockito.Mockito.*
import org.mockito.junit.MockitoJUnitRunner

/**
 * Unit tests for HapticFeedbackHelper
 */
@RunWith(MockitoJUnitRunner::class)
class HapticFeedbackHelperTest {

    @Mock
    private lateinit var hapticFeedback: HapticFeedback
    
    @Mock 
    private lateinit var context: Context
    
    @Mock
    private lateinit var vibrator: Vibrator

    @Test
    fun `performLightHaptic calls hapticFeedback when enabled`() {
        // When: Performing light haptic with feedback enabled
        HapticFeedbackHelper.performLightHaptic(hapticFeedback, enabled = true)
        
        // Then: HapticFeedback should be called
        verify(hapticFeedback).performHapticFeedback(HapticFeedbackType.TextHandleMove)
    }
    
    @Test
    fun `performLightHaptic does not call hapticFeedback when disabled`() {
        // When: Performing light haptic with feedback disabled
        HapticFeedbackHelper.performLightHaptic(hapticFeedback, enabled = false)
        
        // Then: HapticFeedback should not be called
        verify(hapticFeedback, never()).performHapticFeedback(any())
    }
    
    @Test
    fun `performMediumHaptic calls hapticFeedback when enabled`() {
        // When: Performing medium haptic with feedback enabled
        HapticFeedbackHelper.performMediumHaptic(hapticFeedback, enabled = true)
        
        // Then: HapticFeedback should be called with correct type
        verify(hapticFeedback).performHapticFeedback(HapticFeedbackType.LongPress)
    }
    
    @Test
    fun `performMediumHaptic does not call hapticFeedback when disabled`() {
        // When: Performing medium haptic with feedback disabled
        HapticFeedbackHelper.performMediumHaptic(hapticFeedback, enabled = false)
        
        // Then: HapticFeedback should not be called
        verify(hapticFeedback, never()).performHapticFeedback(any())
    }
    
    @Test
    fun `performErrorHaptic does nothing when disabled`() = runBlocking {
        // When: Performing error haptic with feedback disabled
        HapticFeedbackHelper.performErrorHaptic(context, enabled = false)
        
        // Then: Context should not be accessed for vibrator service
        verify(context, never()).getSystemService(any())
    }
    
    @Test
    fun `performSuccessHaptic does nothing when disabled`() = runBlocking {
        // When: Performing success haptic with feedback disabled
        HapticFeedbackHelper.performSuccessHaptic(context, enabled = false)
        
        // Then: Context should not be accessed for vibrator service
        verify(context, never()).getSystemService(any())
    }
    
    @Test
    fun `performRefreshHaptic does nothing when disabled`() = runBlocking {
        // When: Performing refresh haptic with feedback disabled
        HapticFeedbackHelper.performRefreshHaptic(context, enabled = false)
        
        // Then: Context should not be accessed for vibrator service
        verify(context, never()).getSystemService(any())
    }
    
    @Test
    fun `performErrorHaptic accesses vibrator when enabled`() = runBlocking {
        // Given: Context returns vibrator service
        `when`(context.getSystemService(Context.VIBRATOR_SERVICE)).thenReturn(vibrator)
        
        // When: Performing error haptic with feedback enabled
        HapticFeedbackHelper.performErrorHaptic(context, enabled = true)
        
        // Then: Context should access vibrator service
        verify(context).getSystemService(Context.VIBRATOR_SERVICE)
    }
    
    @Test
    fun `performSuccessHaptic accesses vibrator when enabled`() = runBlocking {
        // Given: Context returns vibrator service
        `when`(context.getSystemService(Context.VIBRATOR_SERVICE)).thenReturn(vibrator)
        
        // When: Performing success haptic with feedback enabled
        HapticFeedbackHelper.performSuccessHaptic(context, enabled = true)
        
        // Then: Context should access vibrator service
        verify(context).getSystemService(Context.VIBRATOR_SERVICE)
    }
    
    @Test
    fun `performRefreshHaptic accesses vibrator when enabled`() = runBlocking {
        // Given: Context returns vibrator service
        `when`(context.getSystemService(Context.VIBRATOR_SERVICE)).thenReturn(vibrator)
        
        // When: Performing refresh haptic with feedback enabled
        HapticFeedbackHelper.performRefreshHaptic(context, enabled = true)
        
        // Then: Context should access vibrator service
        verify(context).getSystemService(Context.VIBRATOR_SERVICE)
    }
}