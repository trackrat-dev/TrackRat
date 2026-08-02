package com.trackrat.android.data.models

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for ServerEnvironment, focused on [ServerEnvironment.canonicalize].
 *
 * EnvironmentManager persists the whole ServerEnvironment object (baseURL and
 * all), so an install that selected an environment before its URL changed would
 * keep calling the stale host on every later build. canonicalize is what closes
 * that gap; these tests exercise it with the exact objects such an install would
 * have written, including the real pre-rename staging URL.
 */
class ServerEnvironmentTest {

    /** Exactly what a debug install persisted while Staging pointed at the old host. */
    private val staleStaging = ServerEnvironment(
        name = "Staging",
        baseURL = "https://staging.apiv2.trackrat.net/api/v2/",
        isProduction = false
    )

    @Test
    fun `canonicalize upgrades a stale staging baseURL to the current host`() {
        val resolved = ServerEnvironment.canonicalize(staleStaging)

        assertEquals(
            "stored Staging must adopt the current staging host, not the persisted one",
            ServerEnvironment.staging().baseURL,
            resolved.baseURL
        )
        assertEquals("https://staging-api.trackrat.net/api/v2/", resolved.baseURL)
        assertNotEquals(
            "the pre-rename host must not survive canonicalization",
            staleStaging.baseURL,
            resolved.baseURL
        )
        assertEquals("Staging", resolved.name)
        assertEquals(false, resolved.isProduction)
    }

    @Test
    fun `canonicalize upgrades a stale production baseURL and keeps the production flag`() {
        val staleProduction = ServerEnvironment(
            name = "Production",
            baseURL = "https://old-api.trackrat.net/api/v2/",
            isProduction = true
        )

        val resolved = ServerEnvironment.canonicalize(staleProduction)

        assertEquals(ServerEnvironment.production().baseURL, resolved.baseURL)
        assertEquals("https://apiv2.trackrat.net/api/v2/", resolved.baseURL)
        assertTrue("Production must stay flagged as production", resolved.isProduction)
    }

    @Test
    fun `canonicalize repairs a stale isProduction flag from the current definition`() {
        // A persisted blob can be stale in any field, not just baseURL.
        val mislabeledStaging = ServerEnvironment(
            name = "Staging",
            baseURL = "https://staging.apiv2.trackrat.net/api/v2/",
            isProduction = true
        )

        val resolved = ServerEnvironment.canonicalize(mislabeledStaging)

        assertEquals(
            "Staging must not be treated as production after canonicalization",
            false,
            resolved.isProduction
        )
        assertEquals(ServerEnvironment.staging(), resolved)
    }

    @Test
    fun `canonicalize upgrades a stale local baseURL`() {
        val staleLocal = ServerEnvironment(
            name = "Local",
            baseURL = "http://127.0.0.1:8000/api/v2/",
            isProduction = false
        )

        assertEquals(ServerEnvironment.local(), ServerEnvironment.canonicalize(staleLocal))
    }

    @Test
    fun `canonicalize passes through an environment name it does not recognize`() {
        // getDefaultFromBuildConfig builds an environment named after
        // BuildConfig.ENVIRONMENT_NAME ("Development"), which is not one of the
        // three switchable environments. It must survive untouched.
        val buildConfigEnv = ServerEnvironment(
            name = "Development",
            baseURL = "https://apiv2.trackrat.net/api/v2/",
            isProduction = false
        )

        val resolved = ServerEnvironment.canonicalize(buildConfigEnv)

        assertSame(
            "an unrecognized environment must be returned as-is, not replaced",
            buildConfigEnv,
            resolved
        )
    }

    @Test
    fun `canonicalize leaves current definitions unchanged and is idempotent`() {
        ServerEnvironment.getAvailableEnvironments().forEach { current ->
            val once = ServerEnvironment.canonicalize(current)
            assertEquals("${current.name} must be unchanged when already current", current, once)
            assertEquals(
                "${current.name} must be stable under repeated canonicalization",
                once,
                ServerEnvironment.canonicalize(once)
            )
        }
    }

    @Test
    fun `staging and production point at first-level subdomains covered by Universal SSL`() {
        // Cloudflare Universal SSL covers the apex and ONE subdomain level only
        // (SANs: trackrat.net, *.trackrat.net). A two-label host such as
        // staging.apiv2.trackrat.net fails TLS outright once proxied — the
        // regression that forced the staging rename.
        listOf(ServerEnvironment.production(), ServerEnvironment.staging()).forEach { env ->
            val host = env.baseURL.substringAfter("://").substringBefore("/")
            val labelsBelowApex = host.removeSuffix(".trackrat.net").split(".")
            assertEquals(
                "${env.name} host $host must sit one label below trackrat.net",
                1,
                labelsBelowApex.size
            )
        }
    }

    @Test
    fun `allowsCleartext is true only for the http local environment`() {
        assertEquals(false, ServerEnvironment.production().allowsCleartext)
        assertEquals(false, ServerEnvironment.staging().allowsCleartext)
        assertEquals(true, ServerEnvironment.local().allowsCleartext)
    }

    @Test
    fun `displayName marks non-production environments as DEV`() {
        assertEquals("Production ✓", ServerEnvironment.production().displayName)
        assertEquals("Staging (DEV)", ServerEnvironment.staging().displayName)
        assertEquals("Local (DEV)", ServerEnvironment.local().displayName)
    }
}
