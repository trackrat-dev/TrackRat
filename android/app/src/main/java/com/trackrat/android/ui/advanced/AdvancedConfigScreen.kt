package com.trackrat.android.ui.advanced

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.trackrat.android.data.models.ServerEnvironment
import com.trackrat.android.navigation.TrackRatNavigator

/**
 * Advanced Configuration screen
 * Allows users to switch backend servers and test connections
 * Matches iOS AdvancedConfigurationView
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdvancedConfigScreen(
    viewModel: AdvancedConfigViewModel = hiltViewModel(),
    navigator: TrackRatNavigator
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Advanced Configuration",
                        fontWeight = FontWeight.SemiBold
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navigator.navigateBack() }) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                }
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // Server Environment Section
            item {
                ServerEnvironmentSection(
                    availableEnvironments = uiState.availableEnvironments,
                    selectedEnvironment = uiState.selectedEnvironment,
                    hasChanges = uiState.hasChanges,
                    onEnvironmentSelected = { viewModel.selectEnvironment(it) },
                    onSaveChanges = { viewModel.saveConfiguration() }
                )
            }

            // Health Check Section
            item {
                HealthCheckSection(
                    isTestingConnection = uiState.isTestingConnection,
                    healthCheckResult = uiState.healthCheckResult,
                    onTestConnection = { viewModel.testConnection() }
                )
            }
        }
    }
}

@Composable
private fun ServerEnvironmentSection(
    availableEnvironments: List<ServerEnvironment>,
    selectedEnvironment: ServerEnvironment?,
    hasChanges: Boolean,
    onEnvironmentSelected: (ServerEnvironment) -> Unit,
    onSaveChanges: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f)
            )
            .border(
                width = 1.dp,
                color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f),
                shape = RoundedCornerShape(16.dp)
            )
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "Backend Server",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurface
        )

        Text(
            text = "Choose which backend server to connect to. Production is recommended for normal use.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )

        // Environment options
        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            availableEnvironments.forEach { environment ->
                ServerEnvironmentRow(
                    environment = environment,
                    isSelected = selectedEnvironment?.baseURL == environment.baseURL,
                    onSelect = { onEnvironmentSelected(environment) }
                )
            }
        }

        // Save button (only show if there are changes)
        AnimatedVisibility(
            visible = hasChanges,
            enter = fadeIn() + expandVertically(),
            exit = fadeOut() + shrinkVertically()
        ) {
            Button(
                onClick = onSaveChanges,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFFFF6B35) // TrackRat orange
                )
            ) {
                Icon(
                    imageVector = Icons.Default.CheckCircle,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Save Changes",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
    }
}

@Composable
private fun ServerEnvironmentRow(
    environment: ServerEnvironment,
    isSelected: Boolean,
    onSelect: () -> Unit
) {
    val hapticFeedback = LocalHapticFeedback.current

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(
                if (isSelected)
                    Color(0xFFFF6B35).copy(alpha = 0.2f)
                else
                    MaterialTheme.colorScheme.surface.copy(alpha = 0.05f)
            )
            .border(
                width = 1.dp,
                color = if (isSelected)
                    Color(0xFFFF6B35).copy(alpha = 0.5f)
                else
                    MaterialTheme.colorScheme.outline.copy(alpha = 0.1f),
                shape = RoundedCornerShape(12.dp)
            )
            .clickable {
                hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                onSelect()
            }
            .padding(16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(
            modifier = Modifier.weight(1f)
        ) {
            Text(
                text = environment.name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = environment.baseURL,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
        }

        // Selection indicator
        if (isSelected) {
            Icon(
                imageVector = Icons.Default.CheckCircle,
                contentDescription = "Selected",
                tint = Color(0xFFFF6B35),
                modifier = Modifier.size(24.dp)
            )
        } else {
            Box(
                modifier = Modifier
                    .size(24.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .border(
                        width = 2.dp,
                        color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f),
                        shape = RoundedCornerShape(12.dp)
                    )
            )
        }
    }
}

@Composable
private fun HealthCheckSection(
    isTestingConnection: Boolean,
    healthCheckResult: com.trackrat.android.data.models.HealthCheckResult?,
    onTestConnection: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f)
            )
            .border(
                width = 1.dp,
                color = MaterialTheme.colorScheme.outline.copy(alpha = 0.2f),
                shape = RoundedCornerShape(16.dp)
            )
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "Backend Server Health",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurface
        )

        Text(
            text = "Test the connection to the selected backend server.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )

        // Test Connection Button
        Button(
            onClick = onTestConnection,
            enabled = !isTestingConnection,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (isTestingConnection)
                    MaterialTheme.colorScheme.surfaceVariant
                else
                    Color(0xFFFF6B35)
            )
        ) {
            if (isTestingConnection) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = MaterialTheme.colorScheme.onSurface,
                    strokeWidth = 2.dp
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Testing...")
            } else {
                Text(
                    text = "Test Connection",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }
        }

        // Health Check Result
        AnimatedVisibility(
            visible = healthCheckResult != null,
            enter = fadeIn() + expandVertically(),
            exit = fadeOut() + shrinkVertically()
        ) {
            healthCheckResult?.let { result ->
                HealthCheckResultCard(result)
            }
        }
    }
}

@Composable
private fun HealthCheckResultCard(result: com.trackrat.android.data.models.HealthCheckResult) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(
                if (result.success)
                    Color(0xFF4CAF50).copy(alpha = 0.15f)
                else
                    Color(0xFFF44336).copy(alpha = 0.15f)
            )
            .border(
                width = 1.dp,
                color = if (result.success)
                    Color(0xFF4CAF50).copy(alpha = 0.3f)
                else
                    Color(0xFFF44336).copy(alpha = 0.3f),
                shape = RoundedCornerShape(8.dp)
            )
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // Status header
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Icon(
                imageVector = if (result.success) Icons.Default.CheckCircle else Icons.Default.CheckCircle,
                contentDescription = null,
                tint = if (result.success) Color(0xFF4CAF50) else Color(0xFFF44336),
                modifier = Modifier.size(24.dp)
            )
            Text(
                text = if (result.success) "Connected" else "Connection Failed",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
        }

        // Details
        Column(
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            result.statusCode?.let { code ->
                DetailRow(label = "Status:", value = "HTTP $code")
            }

            DetailRow(
                label = "Response Time:",
                value = String.format("%.2fs", result.responseTime)
            )

            result.errorMessage?.let { error ->
                DetailRow(label = "Error:", value = error)
            }

            result.responseBody?.let { body ->
                if (result.success) {
                    DetailRow(label = "Response:", value = body)
                }
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
        )
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}
