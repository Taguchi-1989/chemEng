# E2E Test Results - ChemEng v1.0.0
**Date:** 2026-04-05
**URL:** https://chemeng-9ha0.onrender.com/
**Method:** Playwright browser automation (Chrome)

---

## Summary

| # | Test | Result | Details |
|---|------|--------|---------|
| 1 | Page load & layout | PASS | 8 tabs visible, Online status, bilingual labels |
| 2 | Property estimation | PASS | Ethanol vapor pressure = 95.20 kPa at 350K |
| 3 | Distillation column design | PASS | 18 stages, R=2.21, D=1.29m, Qc/Qr=57.7 MW |
| 4 | Mass balance | PASS | Closure 100.0%, F=100, D=38.9, B=61.1 mol/s |
| 5 | Heat balance | PASS | Total duty 261.4 MW, liquid->vapor phase change |
| 6 | Liquid-liquid extraction | PASS | 1 stage, 20% recovery (with immiscibility warning) |
| 7 | Gas absorption | PASS | 8 stages, 97.5% ammonia removal |
| 8 | LCOH (hydrogen cost) | PASS | 4.16 EUR/kg H2, sensitivity analysis charts rendered |
| 9 | Theme toggle | PASS | Dark rgb(10,14,20) <-> Light rgb(240,244,248) |
| 10 | History & dashboard | PASS | 7 history entries recorded, dashboard UI functional |
| 11 | Export buttons | PASS | JSON/CSV/Template buttons visible on all results |
| 12 | Footer version | PASS | "ChemEng v1.0.0 - Updated 2026-04-05" displayed |

**Result: 12/12 PASS**

---

## Detailed Results

### Test 2: Property Estimation
- Substance: ethanol
- Property: vapor_pressure
- Temperature: 350 K
- Pressure: 101325 Pa
- Result: 95.2035 kPa

### Test 3: Distillation Column Design
- System: ethanol / water
- Feed: 100 kmol/h, zF=0.4
- Distillate purity: 0.95, Bottoms purity: 0.98
- Theoretical stages: 18, Feed stage: 10
- Reflux ratio: 2.21 (R_min factor 1.3)
- Column diameter: 1.29 m
- Condenser duty: 57.7 MW, Reboiler duty: 57.7 MW

### Test 4: Mass Balance
- System: ethanol / water
- Feed: 100 mol/s, Distillate: 38.9, Bottoms: 61.1
- Mass closure: 100.00%

### Test 5: Heat Balance
- Substance: water, 100 mol/s
- Inlet: 300 K (liquid), Outlet: 400 K (vapor)
- Sensible heat: 35,708 kW
- Latent heat: 225,647 kW
- Total duty: 261,355 kW
- Boiling point detected: 373.1 K
- Phase change: Yes (liquid -> vapor)

### Test 6: Liquid-Liquid Extraction
- System: acetic_acid from water using ethyl_acetate
- Feed: 100 kmol/h, Solvent: 50 kmol/h
- Recovery: 20%, Stages: 1
- Warning: Partially miscible system detected

### Test 7: Gas Absorption
- System: ammonia into water
- Gas in: 100 kmol/h, y_in=0.05
- Removal: 97.5%, Stages: 8
- Absorption factor: 1.350, L/G ratio: 7.728
- Absorbed: 4.874 kmol/h

### Test 8: LCOH
- Method: PEM Electrolysis
- LCOH: 4.16 EUR/kg H2
- Breakdown: CAPEX 26.2%, Energy 60.2%, OPEX 9.0%, Stack 4.1%, Water 0.4%
- Annual production: 800 ton/year
- Total CAPEX: 10.00 M EUR
- Energy efficiency: 78.8%
- CO2 intensity: 0.00 kg/kg H2
- Sensitivity analysis: 3 charts (electricity, CAPEX, operating hours)

### Test 9: Theme Toggle
- Dark mode background: rgb(10, 14, 20)
- Light mode background: rgb(240, 244, 248)
- Toggle works bidirectionally

### Test 10: History & Dashboard
- History entries: 7 (all calculations recorded)
- Dashboard: filter by type, "Save to Dashboard" button on each result
- Compare Selected function available

### Test 12: Footer
- Text: "ChemEng v1.0.0 - Updated 2026-04-05"
- Links: GitHub, API Documentation
- Powered by: thermo/chemicals

---

## Environment
- Browser: Chrome (Playwright MCP)
- Platform: Windows 11
- Deployment: Render (render.yaml)
- Commit: 05d3aa2
