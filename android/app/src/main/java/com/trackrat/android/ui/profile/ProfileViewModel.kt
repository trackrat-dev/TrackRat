package com.trackrat.android.ui.profile

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.preferences.EnvironmentManager
import com.trackrat.android.data.models.ServerEnvironment
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * ViewModel for Profile screen
 * Manages external links and environment display
 */
@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val application: Application,
    private val environmentManager: EnvironmentManager
) : ViewModel() {

    data class UiState(
        val currentEnvironment: ServerEnvironment? = null,
        val canSwitchEnvironments: Boolean = false
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = combine(
        _uiState,
        environmentManager.currentEnvironmentFlow
    ) { state, environment ->
        state.copy(
            currentEnvironment = environment,
            canSwitchEnvironments = environmentManager.canSwitchEnvironments()
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = UiState()
    )

    /**
     * Open Signal support group
     */
    fun openSignalLink() {
        openUrl("https://signal.me/#eu/iG3LNnu-IycTUbwrWF1nwrlR-u-TN5gtBO0tXtJk3Nder7TtfzFPa6On6N9dl3e-")
    }

    /**
     * Open YouTube channel
     */
    fun openYouTube() {
        openUrl("https://www.youtube.com/@TrackRat-Development/shorts")
    }

    /**
     * Open Instagram profile
     */
    fun openInstagram() {
        openUrl("https://www.instagram.com/trackratapp/")
    }

    /**
     * Open URL in external browser
     */
    private fun openUrl(url: String) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
        application.startActivity(intent)
    }
}
