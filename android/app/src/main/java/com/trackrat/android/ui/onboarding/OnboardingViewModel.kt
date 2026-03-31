package com.trackrat.android.ui.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.preferences.UserPreferencesRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * ViewModel for onboarding flow
 * Manages home/work station selection and onboarding completion
 */
@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val preferences: UserPreferencesRepository
) : ViewModel() {

    private val _homeStation = MutableStateFlow<String?>(null)
    val homeStation: StateFlow<String?> = _homeStation.asStateFlow()

    private val _workStation = MutableStateFlow<String?>(null)
    val workStation: StateFlow<String?> = _workStation.asStateFlow()

    /**
     * Set home station for commute suggestions
     */
    fun setHomeStation(stationCode: String?) {
        _homeStation.value = stationCode
    }

    /**
     * Set work station for commute suggestions
     */
    fun setWorkStation(stationCode: String?) {
        _workStation.value = stationCode
    }

    /**
     * Complete onboarding and save preferences
     */
    suspend fun completeOnboarding() {
        viewModelScope.launch {
            // Save home/work stations if set
            preferences.setHomeStation(_homeStation.value)
            preferences.setWorkStation(_workStation.value)

            // Mark onboarding as complete (we'll add this preference)
            // For now, the fact that home/work stations are set indicates onboarding completion
        }
    }
}
