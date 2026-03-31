package com.trackrat.android.ui.advanced

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.trackrat.android.data.models.HealthCheckResult
import com.trackrat.android.data.models.ServerEnvironment
import com.trackrat.android.data.preferences.EnvironmentManager
import com.trackrat.android.data.services.BackendHealthService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * ViewModel for Advanced Configuration screen
 * Handles server environment switching and health checks
 * Matches iOS AdvancedConfigurationView functionality
 */
@HiltViewModel
class AdvancedConfigViewModel @Inject constructor(
    private val environmentManager: EnvironmentManager,
    private val healthService: BackendHealthService
) : ViewModel() {

    data class UiState(
        val currentEnvironment: ServerEnvironment? = null,
        val selectedEnvironment: ServerEnvironment? = null,
        val availableEnvironments: List<ServerEnvironment> = emptyList(),
        val hasChanges: Boolean = false,
        val healthCheckResult: HealthCheckResult? = null,
        val isTestingConnection: Boolean = false
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = combine(
        _uiState,
        environmentManager.currentEnvironmentFlow
    ) { state, currentEnv ->
        state.copy(
            currentEnvironment = currentEnv,
            availableEnvironments = ServerEnvironment.getAvailableEnvironments()
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = UiState()
    )

    init {
        loadCurrentEnvironment()
    }

    /**
     * Load the current environment on init
     */
    private fun loadCurrentEnvironment() {
        viewModelScope.launch {
            val current = environmentManager.loadServerEnvironment()
            _uiState.update { it.copy(
                selectedEnvironment = current
            )}
        }
    }

    /**
     * Select a new environment
     */
    fun selectEnvironment(environment: ServerEnvironment) {
        _uiState.update {
            it.copy(
                selectedEnvironment = environment,
                hasChanges = environment.baseURL != it.currentEnvironment?.baseURL,
                healthCheckResult = null // Clear previous health check
            )
        }
    }

    /**
     * Save the selected environment
     */
    fun saveConfiguration() {
        viewModelScope.launch {
            val selected = _uiState.value.selectedEnvironment ?: return@launch
            environmentManager.saveServerEnvironment(selected)

            _uiState.update { it.copy(
                hasChanges = false
            )}
        }
    }

    /**
     * Test connection to the selected environment
     */
    fun testConnection() {
        val selected = _uiState.value.selectedEnvironment ?: return

        _uiState.update { it.copy(
            isTestingConnection = true,
            healthCheckResult = null
        )}

        viewModelScope.launch {
            try {
                val result = healthService.performHealthCheck(selected)
                _uiState.update { it.copy(
                    healthCheckResult = result,
                    isTestingConnection = false
                )}
            } catch (e: Exception) {
                _uiState.update { it.copy(
                    healthCheckResult = HealthCheckResult(
                        success = false,
                        responseTime = 0.0,
                        errorMessage = e.message ?: "Unknown error"
                    ),
                    isTestingConnection = false
                )}
            }
        }
    }
}
