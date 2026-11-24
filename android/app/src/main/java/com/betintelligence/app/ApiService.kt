package com.betintelligence.app

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface ApiService {
    @GET("/") suspend fun health(): Map<String, String>
    @GET("api/v1/catalog/leagues") suspend fun leagues(@Query("limit") limit: Int = 200): List<CatalogOption>
    @GET("api/v1/catalog/teams") suspend fun teams(@Query("limit") limit: Int = 200): List<CatalogOption>
    @GET("api/v1/analytics/pre-match") suspend fun analyze(@Query("league_id") leagueId: Int, @Query("home_team_id") homeTeamId: Int, @Query("away_team_id") awayTeamId: Int): MatchAnalysis
    @POST("api/v1/analytics/value") suspend fun evaluateValue(@Body request: OddsValueRequest): OddsValueResponse
}

object ApiFactory {
    fun create(baseUrl: String): ApiService {
        val normalized = baseUrl.trim().trimEnd('/') + "/"
        require(normalized.startsWith("https://")) { "Gunakan URL backend HTTPS yang aman." }
        return Retrofit.Builder().baseUrl(normalized).addConverterFactory(GsonConverterFactory.create()).build().create(ApiService::class.java)
    }
}
