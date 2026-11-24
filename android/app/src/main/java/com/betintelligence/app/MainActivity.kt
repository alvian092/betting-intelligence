package com.betintelligence.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { BettingIntelligenceApp() }
    }
}

private val AppColors = darkColorScheme(
    primary = Color(0xFF63D6B1),
    secondary = Color(0xFF8CA9FF),
    background = Color(0xFF08111F),
    surface = Color(0xFF111E30),
    onPrimary = Color(0xFF07131B),
    onBackground = Color(0xFFEAF0F7),
    onSurface = Color(0xFFEAF0F7)
)

@Composable
fun BettingIntelligenceApp() {
    val context = LocalContext.current
    val preferences = remember { context.getSharedPreferences("betting_intelligence", 0) }
    val scope = rememberCoroutineScope()

    var baseUrl by remember { mutableStateOf(preferences.getString("api_url", "") ?: "") }
    var api by remember { mutableStateOf<ApiService?>(null) }
    var connected by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf("Masukkan alamat backend HTTPS untuk mulai.") }
    var leagues by remember { mutableStateOf<List<CatalogOption>>(emptyList()) }
    var teams by remember { mutableStateOf<List<CatalogOption>>(emptyList()) }
    var selectedLeague by remember { mutableStateOf<CatalogOption?>(null) }
    var selectedHome by remember { mutableStateOf<CatalogOption?>(null) }
    var selectedAway by remember { mutableStateOf<CatalogOption?>(null) }
    var analysis by remember { mutableStateOf<MatchAnalysis?>(null) }
    var oddsHome by remember { mutableStateOf("") }
    var oddsDraw by remember { mutableStateOf("") }
    var oddsAway by remember { mutableStateOf("") }
    var valueResult by remember { mutableStateOf<OddsValueResponse?>(null) }

    fun connect() {
        scope.launch {
            busy = true
            connected = false
            analysis = null
            valueResult = null
            try {
                val service = ApiFactory.create(baseUrl)
                service.health()
                val loadedLeagues = service.leagues()
                val loadedTeams = service.teams()
                api = service
                leagues = loadedLeagues
                teams = loadedTeams
                selectedLeague = null
                selectedHome = null
                selectedAway = null
                preferences.edit().putString("api_url", baseUrl.trim().trimEnd('/')).apply()
                connected = true
                notice = "Terhubung. ${loadedLeagues.size} liga dan ${loadedTeams.size} tim dimuat."
            } catch (error: Exception) {
                api = null
                notice = "Koneksi gagal: ${error.message ?: "periksa URL dan status backend"}"
            } finally {
                busy = false
            }
        }
    }

    fun runAnalysis() {
        val service = api ?: return
        val league = selectedLeague ?: return
        val home = selectedHome ?: return
        val away = selectedAway ?: return
        if (home.id == away.id) {
            notice = "Tim kandang dan tandang harus berbeda."
            return
        }
        scope.launch {
            busy = true
            analysis = null
            valueResult = null
            try {
                analysis = service.analyze(league.id, home.id, away.id)
                notice = "Analisis selesai. Estimasi model tetap bersifat probabilistik."
            } catch (error: Exception) {
                notice = "Analisis gagal: ${error.message ?: "periksa data historis"}"
            } finally {
                busy = false
            }
        }
    }

    fun evaluateOdds() {
        val service = api ?: return
        val result = analysis ?: return
        val prices = listOf(oddsHome.toDoubleOrNull(), oddsDraw.toDoubleOrNull(), oddsAway.toDoubleOrNull())
        if (prices.any { it == null || it <= 1.0 }) {
            notice = "Masukkan tiga odds desimal yang valid (lebih dari 1.00)."
            return
        }
        val p = result.markets.oneXTwo
        val request = OddsValueRequest(
            selections = listOf(
                OddsSelection(selectedHome?.name ?: "Home", p.home, prices[0]!!),
                OddsSelection("Draw", p.draw, prices[1]!!),
                OddsSelection(selectedAway?.name ?: "Away", p.away, prices[2]!!)
            )
        )
        scope.launch {
            busy = true
            valueResult = null
            try {
                valueResult = service.evaluateValue(request)
                notice = "Evaluasi odds selesai. Periksa EV dan status NO BET/VALUE."
            } catch (error: Exception) {
                notice = "Evaluasi odds gagal: ${error.message ?: "periksa input"}"
            } finally {
                busy = false
            }
        }
    }

    MaterialTheme(colorScheme = AppColors) {
        Surface(modifier = Modifier.fillMaxSize(), color = AppColors.background) {
            Column(
                modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("BETTING INTELLIGENCE", color = AppColors.primary, fontSize = 13.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
                    Text("Find the Value, Not Just the Winner.", fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Text("Poisson · Dixon–Coles · Value Engine", color = Color(0xFF9EACC0), fontSize = 13.sp)
                }

                Card(colors = CardDefaults.cardColors(containerColor = AppColors.surface)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Koneksi backend", fontWeight = FontWeight.Bold, fontSize = 17.sp)
                        OutlinedTextField(
                            value = baseUrl,
                            onValueChange = { baseUrl = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Backend URL (HTTPS)") },
                            placeholder = { Text("https://alamat-api-anda") },
                            singleLine = true
                        )
                        Button(onClick = { connect() }, enabled = !busy && baseUrl.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                            Text(if (busy) "Memproses…" else "Simpan & hubungkan")
                        }
                        Text(notice, color = if (connected) AppColors.primary else Color(0xFFB8C5D6), fontSize = 12.sp)
                    }
                }

                if (connected) {
                    Card(colors = CardDefaults.cardColors(containerColor = AppColors.surface)) {
                        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text("Pilih pertandingan", fontWeight = FontWeight.Bold, fontSize = 17.sp)
                            OptionDropdown("Liga", selectedLeague, leagues) {
                                selectedLeague = it
                                selectedHome = null
                                selectedAway = null
                                analysis = null
                            }
                            OptionDropdown("Tim kandang", selectedHome, teams) {
                                selectedHome = it
                                analysis = null
                            }
                            OptionDropdown("Tim tandang", selectedAway, teams) {
                                selectedAway = it
                                analysis = null
                            }
                            Button(
                                onClick = { runAnalysis() },
                                enabled = !busy && selectedLeague != null && selectedHome != null && selectedAway != null && selectedHome?.id != selectedAway?.id,
                                modifier = Modifier.fillMaxWidth()
                            ) { Text(if (busy) "Menghitung…" else "Analisis pertandingan") }
                        }
                    }
                }

                analysis?.let { result ->
                    Card(colors = CardDefaults.cardColors(containerColor = AppColors.surface)) {
                        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text("Hasil analisis", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                Metric("λ kandang", result.parameters.homeLambda)
                                Metric("λ tandang", result.parameters.awayLambda)
                            }
                            Text("Probabilitas 1X2", fontWeight = FontWeight.SemiBold)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Probability("1", result.markets.oneXTwo.home)
                                Probability("X", result.markets.oneXTwo.draw)
                                Probability("2", result.markets.oneXTwo.away)
                            }
                            Text("Pasar lainnya", fontWeight = FontWeight.SemiBold)
                            ResultLine("Double chance 1X", result.markets.doubleChance.oneX)
                            ResultLine("Double chance X2", result.markets.doubleChance.x2)
                            ResultLine("Over 2.5", result.markets.totals.over)
                            ResultLine("Under 2.5", result.markets.totals.under)
                            ResultLine("BTTS Ya", result.markets.btts.yes)
                            ResultLine("BTTS Tidak", result.markets.btts.no)
                            Text("Top correct score", fontWeight = FontWeight.SemiBold)
                            result.markets.topScores.take(6).forEach { score ->
                                ResultLine(score.score, score.probability)
                            }
                            Text("Odds & Value Engine", fontWeight = FontWeight.Bold, fontSize = 17.sp)
                            OutlinedTextField(value = oddsHome, onValueChange = { oddsHome = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Odds ${selectedHome?.name ?: "Home"}") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true)
                            OutlinedTextField(value = oddsDraw, onValueChange = { oddsDraw = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Odds Draw") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true)
                            OutlinedTextField(value = oddsAway, onValueChange = { oddsAway = it }, modifier = Modifier.fillMaxWidth(), label = { Text("Odds ${selectedAway?.name ?: "Away"}") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true)
                            OutlinedButton(onClick = { evaluateOdds() }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text("Hitung EV & Kelly") }
                            valueResult?.let { value ->
                                Text("Margin bookmaker: ${"%.2f".format(value.bookmakerMarginPercent)}%", color = AppColors.secondary)
                                value.selections.forEach { item ->
                                    ResultLine("${item.name} · ${item.decision} · EV ${"%.1f".format(item.ev * 100)}%", item.recommendedStakeFraction)
                                }
                            }
                            Text("Status model: ${result.status}. Estimasi bukan jaminan hasil atau profit.", color = Color(0xFF9EACC0), fontSize = 11.sp)
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
            }
        }
    }
}

@Composable
private fun OptionDropdown(label: String, selected: CatalogOption?, options: List<CatalogOption>, onSelect: (CatalogOption) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        OutlinedTextField(
            value = selected?.name ?: "",
            onValueChange = {},
            modifier = Modifier.fillMaxWidth(),
            label = { Text(label) },
            placeholder = { Text("Pilih $label") },
            readOnly = true,
            singleLine = true
        )
        Box(Modifier.matchParentSize().clickable { expanded = true })
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }, modifier = Modifier.fillMaxWidth(0.9f)) {
            options.forEach { option ->
                DropdownMenuItem(text = { Text(option.name) }, onClick = {
                    onSelect(option)
                    expanded = false
                })
            }
        }
    }
}

@Composable
private fun Metric(label: String, value: Double) {
    Card(modifier = Modifier.fillMaxWidth(0.48f), colors = CardDefaults.cardColors(containerColor = Color(0xFF1B2B40))) {
        Column(Modifier.padding(12.dp)) {
            Text(label, color = Color(0xFF9EACC0), fontSize = 12.sp)
            Text("%.3f".format(value), fontSize = 22.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun Probability(label: String, value: Double) {
    Card(modifier = Modifier.fillMaxWidth(0.31f), colors = CardDefaults.cardColors(containerColor = Color(0xFF1B2B40))) {
        Column(Modifier.padding(10.dp)) {
            Text(label, color = Color(0xFF9EACC0))
            Text("${"%.1f".format(value * 100)}%", fontSize = 20.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun ResultLine(label: String, value: Double) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = Color(0xFFB8C5D6), fontSize = 13.sp)
        Text("${"%.1f".format(value * 100)}%", fontWeight = FontWeight.SemiBold, color = AppColors.primary)
    }
}
