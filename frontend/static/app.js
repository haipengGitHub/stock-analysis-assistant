// 股票分析助手 - 前端逻辑

let currentSymbol = 'AAPL';
let currentPeriod = '3mo';
let priceChart = null;

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    loadSuggestions();

    // 输入框事件
    const input = document.getElementById('stockInput');
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            analyzeStock();
        }
    });

    input.addEventListener('input', (e) => {
        const value = e.target.value.trim();
        if (value.length > 0) {
            searchStocks(value);
        } else {
            hideSuggestions();
        }
    });

    // 点击外部关闭建议
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-box')) {
            hideSuggestions();
        }
    });

    // 初始加载
    analyzeStock();
});

// 加载热门股票建议
async function loadSuggestions() {
    try {
        const response = await fetch('/api/suggestions');
        const data = await response.json();
        showSuggestions(data.suggestions);
    } catch (error) {
        console.error('加载建议失败:', error);
    }
}

// 搜索股票
async function searchStocks(query) {
    try {
        const response = await fetch(`/api/search/${encodeURIComponent(query)}`);
        const data = await response.json();
        showSuggestions(data.results);
    } catch (error) {
        console.error('搜索失败:', error);
    }
}

// 显示建议
function showSuggestions(suggestions) {
    const container = document.getElementById('suggestions');
    if (!suggestions || suggestions.length === 0) {
        hideSuggestions();
        return;
    }

    container.innerHTML = suggestions.map(s => `
        <div class="suggestion-item" onclick="selectStock('${s.symbol}')">
            <span class="suggestion-symbol">${s.symbol}</span>
            <span class="suggestion-name">${s.name}</span>
        </div>
    `).join('');
    container.classList.add('show');
}

// 隐藏建议
function hideSuggestions() {
    document.getElementById('suggestions').classList.remove('show');
}

// 选择股票
function selectStock(symbol) {
    document.getElementById('stockInput').value = symbol;
    hideSuggestions();
    analyzeStock();
}

// 分析股票
async function analyzeStock() {
    const symbol = document.getElementById('stockInput').value.trim().toUpperCase();
    if (!symbol) return;

    currentSymbol = symbol;
    showLoading();
    hideError();

    try {
        const response = await fetch(`/api/stock/${symbol}?period=${currentPeriod}`);

        if (!response.ok) {
            const error = await response.json();
            const detail = error.detail;
            const message = Array.isArray(detail)
                ? detail.map((d) => d.msg || d).join('; ')
                : (detail || '分析失败');
            throw new Error(message);
        }

        const data = await response.json();
        displayResults(data);
    } catch (error) {
        showError(error.message);
        hideMainContent();
    } finally {
        hideLoading();
    }
}

// 显示加载状态
function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('searchBtn').disabled = true;
    document.getElementById('searchBtn').textContent = '分析中...';
}

// 隐藏加载状态
function hideLoading() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('searchBtn').disabled = false;
    document.getElementById('searchBtn').textContent = '分析';
}

// 显示错误
function showError(message) {
    const errorEl = document.getElementById('error');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
}

// 隐藏错误
function hideError() {
    document.getElementById('error').style.display = 'none';
}

// 显示主内容
function showMainContent() {
    document.getElementById('mainContent').style.display = 'block';
}

// 隐藏主内容
function hideMainContent() {
    document.getElementById('mainContent').style.display = 'none';
}

// 显示分析结果
function displayResults(data) {
    showMainContent();

    // 股票信息
    document.getElementById('stockName').textContent = data.stock.name;
    document.getElementById('stockSymbol').textContent = data.stock.symbol;
    document.getElementById('currentPrice').textContent = formatPrice(data.stock.current_price);

    const changeEl = document.getElementById('priceChange');
    const changeStr = `${data.stock.change >= 0 ? '+' : ''}${data.stock.change.toFixed(2)} (${data.stock.change_percent >= 0 ? '+' : ''}${data.stock.change_percent.toFixed(2)}%)`;
    changeEl.textContent = changeStr;
    changeEl.className = 'price-change ' + (data.stock.change_percent >= 0 ? 'positive' : 'negative');

    document.getElementById('high52w').textContent = formatPrice(data.stock.high_52w);
    document.getElementById('low52w').textContent = formatPrice(data.stock.low_52w);
    document.getElementById('volume').textContent = formatVolume(data.stock.volume);
    document.getElementById('marketCap').textContent = data.stock.market_cap || '-';

    // 趋势预测
    const trendBadge = document.getElementById('trendBadge');
    const trendIcon = document.getElementById('trendIcon');
    const trendText = document.getElementById('trendText');

    trendBadge.className = 'prediction-badge ' + data.prediction.trend;

    const trendMap = {
        'bullish': { icon: '📈', text: '看涨' },
        'bearish': { icon: '📉', text: '看跌' },
        'neutral': { icon: '📊', text: '中性' }
    };

    trendIcon.textContent = trendMap[data.prediction.trend].icon;
    trendText.textContent = trendMap[data.prediction.trend].text;

    document.getElementById('confidenceFill').style.width = data.prediction.confidence + '%';
    document.getElementById('confidenceValue').textContent = data.prediction.confidence + '%';

    const targetPriceBox = document.getElementById('targetPriceBox');
    if (data.prediction.target_price) {
        targetPriceBox.style.display = 'block';
        document.getElementById('targetPrice').textContent = formatPrice(data.prediction.target_price);
    } else {
        targetPriceBox.style.display = 'none';
    }

    // 分析依据
    const reasonList = document.getElementById('reasonList');
    reasonList.innerHTML = data.prediction.reason.map(r => `<li>${r}</li>`).join('');

    // 技术指标
    const indicatorsGrid = document.getElementById('indicatorsGrid');
    indicatorsGrid.innerHTML = data.indicators.map(ind => {
        const signalMap = {
            'buy': '买入信号',
            'sell': '卖出信号',
            'neutral': '中性'
        };
        return `
            <div class="indicator-card">
                <span class="indicator-name">${ind.name}</span>
                <span class="indicator-value">${typeof ind.value === 'number' ? ind.value.toFixed(2) : ind.value}</span>
                <span class="indicator-signal ${ind.signal}">${signalMap[ind.signal] || ind.signal}</span>
            </div>
        `;
    }).join('');

    // K线图
    renderChart(data.chart_data);
}

// 渲染K线图
function renderChart(chartData) {
    if (!chartData || !chartData.dates || chartData.dates.length === 0) {
        return;
    }

    const chartDom = document.getElementById('priceChart');

    if (priceChart) {
        priceChart.dispose();
    }

    priceChart = echarts.init(chartDom);

    // 计算MA5, MA10, MA20
    const closeData = chartData.close;
    const ma5 = calculateMA(5, closeData);
    const ma10 = calculateMA(10, closeData);
    const ma20 = calculateMA(20, closeData);

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            backgroundColor: 'rgba(30, 41, 59, 0.9)',
            borderColor: '#334155',
            textStyle: {
                color: '#f1f5f9'
            }
        },
        legend: {
            data: ['K线', 'MA5', 'MA10', 'MA20'],
            textStyle: {
                color: '#94a3b8'
            },
            top: 10
        },
        grid: [
            {
                left: '10%',
                right: '8%',
                top: '15%',
                height: '55%'
            },
            {
                left: '10%',
                right: '8%',
                top: '75%',
                height: '15%'
            }
        ],
        xAxis: [
            {
                type: 'category',
                data: chartData.dates,
                scale: true,
                boundaryGap: false,
                axisLine: {
                    lineStyle: {
                        color: '#334155'
                    }
                },
                splitLine: {
                    show: false
                },
                min: 'dataMin',
                max: 'dataMax'
            },
            {
                type: 'category',
                gridIndex: 1,
                data: chartData.dates,
                scale: true,
                boundaryGap: false,
                axisLine: {
                    lineStyle: {
                        color: '#334155'
                    }
                },
                splitLine: {
                    show: false
                },
                axisLabel: {
                    show: false
                },
                min: 'dataMin',
                max: 'dataMax'
            }
        ],
        yAxis: [
            {
                scale: true,
                axisLine: {
                    lineStyle: {
                        color: '#334155'
                    }
                },
                splitLine: {
                    lineStyle: {
                        color: '#334155',
                        opacity: 0.3
                    }
                }
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLine: {
                    lineStyle: {
                        color: '#334155'
                    }
                },
                splitLine: {
                    show: false
                },
                axisLabel: {
                    show: false
                }
            }
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                start: 50,
                end: 100
            },
            {
                show: true,
                xAxisIndex: [0, 1],
                type: 'slider',
                top: '90%',
                start: 50,
                end: 100,
                borderColor: '#334155',
                textStyle: {
                    color: '#94a3b8'
                }
            }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                data: chartData.dates.map((_, i) => [
                    chartData.open[i],
                    chartData.close[i],
                    chartData.low[i],
                    chartData.high[i]
                ]),
                itemStyle: {
                    color: '#10b981',
                    color0: '#ef4444',
                    borderColor: '#10b981',
                    borderColor0: '#ef4444'
                }
            },
            {
                name: 'MA5',
                type: 'line',
                data: ma5,
                smooth: true,
                showSymbol: false,
                lineStyle: {
                    color: '#f59e0b',
                    width: 1.5
                }
            },
            {
                name: 'MA10',
                type: 'line',
                data: ma10,
                smooth: true,
                showSymbol: false,
                lineStyle: {
                    color: '#3b82f6',
                    width: 1.5
                }
            },
            {
                name: 'MA20',
                type: 'line',
                data: ma20,
                smooth: true,
                showSymbol: false,
                lineStyle: {
                    color: '#a78bfa',
                    width: 1.5
                }
            },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: chartData.volume,
                itemStyle: {
                    color: '#3b82f6'
                }
            }
        ]
    };

    priceChart.setOption(option);

    // 响应式
    window.addEventListener('resize', () => {
        priceChart.resize();
    });
}

// 计算移动平均线
function calculateMA(dayCount, data) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < dayCount - 1) {
            result.push('-');
            continue;
        }
        let sum = 0;
        for (let j = 0; j < dayCount; j++) {
            sum += data[i - j];
        }
        result.push((sum / dayCount).toFixed(2));
    }
    return result;
}

// 切换周期
function changePeriod(period) {
    currentPeriod = period;

    // 更新按钮状态
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === period);
    });

    // 重新分析
    analyzeStock();
}

// 格式化价格
function formatPrice(price) {
    if (price >= 1000) {
        return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return '$' + price.toFixed(2);
}

// 格式化成交量
function formatVolume(volume) {
    if (volume >= 1000000000) {
        return (volume / 1000000000).toFixed(2) + 'B';
    }
    if (volume >= 1000000) {
        return (volume / 1000000).toFixed(2) + 'M';
    }
    if (volume >= 1000) {
        return (volume / 1000).toFixed(2) + 'K';
    }
    return volume.toString();
}
