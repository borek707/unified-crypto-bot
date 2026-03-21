# Backtest Results Database

## Structure
- `backtest_results/` - JSON files with detailed results
- `backtest_summary.csv` - Summary table for comparison
- `performance_charts/` - Visualizations

## Latest Results

### 2-Year Backtest (2024-01-01 to 2026-03-01)
| Strategy | Return | Max DD | Trades | Win Rate | vs HODL |
|----------|--------|--------|--------|----------|---------|
| DCA | +55.68% | - | - | - | +7.0% |
| HODL | +48.69% | - | - | - | - |
| GRID | +4.37% | - | 28 | 100% | -44.3% |

### 3-Month Flexible Strategy
| Strategy | Return | Max DD | Trades | Win Rate |
|----------|--------|--------|--------|----------|
| Flexible (Grid+DCA) | +26.16% | 7.28% | 1215 | - |
| Grid LONG | +8.38% | 1.57% | 1368 | - |
| DCA Only | +17.76% | - | - | - |

### Conclusions
- **DCA** works best in bull markets
- **GRID** works best in sideways markets
- **Flexible** strategy adapts and performs well across all conditions
