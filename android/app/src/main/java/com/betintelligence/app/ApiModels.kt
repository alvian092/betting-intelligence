package com.betintelligence.app

import com.google.gson.annotations.SerializedName

data class CatalogOption(val id: Int, val name: String)

data class MatchAnalysis(val model: String, val status: String, val parameters: ModelParameters, val markets: MarketProbabilities)
data class ModelParameters(@SerializedName("home_lambda") val homeLambda: Double, @SerializedName("away_lambda") val awayLambda: Double, val rho: Double)
data class MarketProbabilities(@SerializedName("1x2") val oneXTwo: OutcomeProbabilities, @SerializedName("double_chance") val doubleChance: DoubleChance, @SerializedName("totals_2_5") val totals: Totals, val btts: Btts, @SerializedName("top_correct_scores") val topScores: List<ScoreProbability>)
data class OutcomeProbabilities(val home: Double, val draw: Double, val away: Double)
data class DoubleChance(@SerializedName("1x") val oneX: Double, val x2: Double, @SerializedName("12") val twelve: Double)
data class Totals(val over: Double, val under: Double)
data class Btts(val yes: Double, val no: Double)
data class ScoreProbability(val score: String, val probability: Double)
data class OddsSelection(val name: String, @SerializedName("model_probability") val modelProbability: Double, @SerializedName("decimal_odds") val decimalOdds: Double)
data class OddsValueRequest(val selections: List<OddsSelection>, @SerializedName("fractional_kelly") val fractionalKelly: Double = 0.25, @SerializedName("min_ev") val minEv: Double = 0.02)
data class OddsValueResponse(@SerializedName("bookmaker_margin_percent") val bookmakerMarginPercent: Double, val selections: List<ValueSelection>)
data class ValueSelection(val name: String, @SerializedName("model_fair_odds") val modelFairOdds: Double, val ev: Double, val edge: Double, @SerializedName("recommended_stake_fraction") val recommendedStakeFraction: Double, val decision: String)
