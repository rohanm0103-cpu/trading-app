// ============= INR FORMATTING FUNCTIONS =============
function initTradingCursor() {
    if (window.matchMedia('(hover: none), (pointer: coarse), (prefers-reduced-motion: reduce)').matches) {
        return;
    }

    let glow = document.querySelector('.trading-cursor-glow');
    if (!glow) {
        glow = document.createElement('div');
        glow.className = 'trading-cursor-glow';
        glow.setAttribute('aria-hidden', 'true');
        document.body.appendChild(glow);
    }

    const trails = Array.from({ length: 5 }, (_, index) => {
        const trail = document.createElement('div');
        trail.className = 'trading-cursor-trail';
        trail.setAttribute('aria-hidden', 'true');
        trail.style.transition = `opacity 0.2s ease, transform ${0.08 + index * 0.035}s ease-out`;
        document.body.appendChild(trail);
        return { node: trail, x: 0, y: 0 };
    });

    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;
    let glowX = mouseX;
    let glowY = mouseY;
    let rafId = null;

    function animateCursor() {
        glowX += (mouseX - glowX) * 0.18;
        glowY += (mouseY - glowY) * 0.18;
        glow.style.left = `${glowX}px`;
        glow.style.top = `${glowY}px`;

        trails.forEach((trail, index) => {
            const target = index === 0 ? { x: mouseX, y: mouseY } : trails[index - 1];
            trail.x += (target.x - trail.x) * (0.34 - index * 0.03);
            trail.y += (target.y - trail.y) * (0.34 - index * 0.03);
            trail.node.style.left = `${trail.x}px`;
            trail.node.style.top = `${trail.y}px`;
            trail.node.style.transform = `translate(-50%, -50%) scale(${1 - index * 0.12})`;
        });

        rafId = requestAnimationFrame(animateCursor);
    }

    window.addEventListener('mousemove', (event) => {
        mouseX = event.clientX;
        mouseY = event.clientY;
        document.body.classList.add('trading-cursor-active');
        if (!rafId) {
            animateCursor();
        }
    });

    window.addEventListener('mouseleave', () => {
        document.body.classList.remove('trading-cursor-active');
    });
}

function formatINR(amount) {
    if (amount >= 10000000) {
        return '₹' + (amount / 10000000).toFixed(2) + ' Cr';
    } else if (amount >= 100000) {
        return '₹' + (amount / 100000).toFixed(2) + ' L';
    } else if (amount >= 1000) {
        return '₹' + amount.toLocaleString('en-IN');
    }
    return '₹' + amount.toFixed(2);
}

function formatRupees(amount) {
    return '₹' + Math.abs(amount).toLocaleString('en-IN', { 
        minimumFractionDigits: 2, 
        maximumFractionDigits: 2 
    });
}


// ================= REALTIME PRICE MEMORY =================
let previousPrices = {};   // For ticker/grid price change detection
let lastPrices = {};       // For holdings P&L calculations


// ============= TAB NAVIGATION =============
function switchSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.page-section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Remove active class from all nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    
    // Show target section
    const target = document.getElementById(sectionId);
    if (target) {
        target.classList.add('active');
    }
    
    // Add active class to clicked nav link
    const activeLink = document.querySelector(`.nav-link[data-section="${sectionId}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    // If switching to markets section, fetch stocks
    if (sectionId === 'markets-section') {
        fetchStocks();
    }
    
    // If switching to holdings, refresh portfolio
    if (sectionId === 'holdings-section') {
        fetchPortfolio();
    }
}


// ============= INITIAL LOAD =============
document.addEventListener('DOMContentLoaded', () => {
    initTradingCursor();

    // Initialize nav link click handlers
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetSection = this.getAttribute('data-section');
            switchSection(targetSection);
        });
    });
    
    // Load initial data for home page
    if (document.getElementById('homeStocksGrid')) {
        fetchStocks();
        setInterval(fetchStocks, 5000); // Auto-refresh every 5 seconds
    }
    
    // Initialize portfolio if on dashboard/holdings page
    if (document.getElementById('holdingsTableBody') || document.getElementById('holdingsTable')) {
        fetchPortfolio();
    }
    
    // Initialize auth forms if present
    initAuthForms();
    
    // Initialize trade form if present
    initTradeForm();
});


// ============= AUTH FUNCTIONS =============
function initAuthForms() {
    // Login Form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username')?.value;
            const password = document.getElementById('password')?.value;
            
            if (!username || !password) {
                showMessage('message', 'Please enter username and password', 'error');
                return;
            }
            
            const btn = loginForm.querySelector('button[type="submit"]');
            const originalBtnText = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging in...';
            btn.disabled = true;
            
            try {
                const res = await fetch('/api/login/user', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    credentials: 'include',
                    body: JSON.stringify({username, password})
                });
                const data = await res.json();
                
                if (res.ok) {
                    showMessage('message', '✅ Login successful! Redirecting...', 'success');
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1000);
                } else {
                    showMessage('message', '❌ ' + (data.error || 'Invalid credentials'), 'error');
                    btn.innerHTML = originalBtnText;
                    btn.disabled = false;
                }
            } catch (err) {
                console.error('Login error:', err);
                showMessage('message', '❌ Connection error. Please try again.', 'error');
                btn.innerHTML = originalBtnText;
                btn.disabled = false;
            }
        });
    }

    // Signup Form
    const signupForm = document.getElementById('signupForm');
    if (signupForm) {
        signupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('signupUsername')?.value;
            const email = document.getElementById('signupEmail')?.value;
            const password = document.getElementById('signupPassword')?.value;
            const confirm = document.getElementById('confirmPassword')?.value;
            
            // Validate
            if (password !== confirm) {
                showMessage('signupMessage', '❌ Passwords do not match!', 'error');
                return;
            }
            if (password.length < 6) {
                showMessage('signupMessage', '❌ Password must be at least 6 characters', 'error');
                return;
            }
            
            const btn = signupForm.querySelector('button[type="submit"]');
            const originalBtnText = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating account...';
            btn.disabled = true;
            
            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    credentials: 'include',
                    body: JSON.stringify({username, email, password})
                });
                const data = await res.json();
                
                if (res.ok) {
                    showMessage('signupMessage', '✅ Account created! Redirecting to login...', 'success');
                    setTimeout(() => {
                        if (typeof showTab === 'function') {
                            showTab('login');
                            document.getElementById('username').value = username;
                        }
                    }, 1500);
                } else {
                    showMessage('signupMessage', '❌ ' + (data.error || 'Registration failed'), 'error');
                    btn.innerHTML = originalBtnText;
                    btn.disabled = false;
                }
            } catch (err) {
                console.error('Signup error:', err);
                showMessage('signupMessage', '❌ Connection error. Please try again.', 'error');
                btn.innerHTML = originalBtnText;
                btn.disabled = false;
            }
        });
    }

    // Logout Button
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                await fetch('/logout', {
                    method: 'GET',
                    credentials: 'include'
                });
                window.location.href = '/';
            } catch (err) {
                console.error('Logout error:', err);
            }
        });
    }
}


// ============= MARKET DATA =============
async function fetchStocks() {
    try {
        const res = await fetch('/api/stocks');
        if (!res.ok) throw new Error('Failed to fetch stocks');
        
        const stocks = await res.json();
        updateTicker(stocks);
        renderStocks(stocks);
        populateStockSelect(stocks);
    } catch (err) {
        console.error('Failed to fetch stocks:', err);
        // Fallback data for demo
        const fallback = [
            { symbol: 'RELIANCE', current_price: 2850.50, change_percent: 1.2, name: 'Reliance Industries' },
            { symbol: 'TCS', current_price: 3680.30, change_percent: -0.5, name: 'Tata Consultancy Services' },
            { symbol: 'HDFCBANK', current_price: 1645.80, change_percent: 0.8, name: 'HDFC Bank' },
            { symbol: 'INFY', current_price: 1520.25, change_percent: 1.5, name: 'Infosys' },
            { symbol: 'ICICIBANK', current_price: 1085.60, change_percent: -0.2, name: 'ICICI Bank' }
        ];
        updateTicker(fallback);
        renderStocks(fallback);
        populateStockSelect(fallback);
    }
}


// ============= STOCK TICKER =============
function updateTicker(stocks) {
    const ticker = document.getElementById('marketTicker');
    if (!ticker) return;
    
    ticker.innerHTML = stocks.map(stock => {
        const symbol = stock.symbol;
        const price = stock.current_price;
        const change = stock.change_percent;
        const isUp = change >= 0;
        
        const prevPrice = previousPrices[symbol];
        const priceClass = prevPrice !== undefined ? 
            (price > prevPrice ? 'price-up' : price < prevPrice ? 'price-down' : '') : '';
        
        previousPrices[symbol] = price;
        
        return `
            <div class="ticker-item ${priceClass}">
                <strong>${symbol}</strong> ${formatRupees(price)} 
                <span class="${isUp ? 'up' : 'down'}">
                    ${isUp ? '▲' : '▼'} ${Math.abs(change).toFixed(2)}%
                </span>
            </div>
        `;
    }).join('');
}


// ============= STOCK GRID =============
function renderStocks(stocks) {
    const container = document.getElementById('homeStocksGrid');
    if (!container) return;
    
    container.innerHTML = stocks.map(stock => {
        const isUp = stock.change_percent >= 0;
        return `
            <div class="stock-card ${isUp ? 'positive' : 'negative'}">
                <div class="stock-header">
                    <strong>${stock.symbol}</strong>
                    <span class="${isUp ? 'up' : 'down'}">
                        ${isUp ? '+' : ''}${stock.change_percent.toFixed(2)}%
                    </span>
                </div>
                <div class="stock-price">${formatRupees(stock.current_price)}</div>
                <small style="color: var(--secondary)">${stock.name}</small>
                <button class="btn-sm btn-secondary" style="margin-top: 0.5rem;" 
                        onclick="quickTrade('${stock.symbol}', ${stock.current_price})">
                    <i class="fas fa-exchange-alt"></i> Trade
                </button>
            </div>
        `;
    }).join('');
}


// ============= POPULATE STOCK SELECT =============
function populateStockSelect(stocks) {
    const select = document.getElementById('stockSymbol');
    if (!select) return;
    
    const defaultOption = select.querySelector('option[value=""]');
    select.innerHTML = '';
    if (defaultOption) select.appendChild(defaultOption);
    
    stocks.forEach(stock => {
        const opt = document.createElement('option');
        opt.value = stock.symbol;
        opt.textContent = `${stock.symbol} - ${formatRupees(stock.current_price)}`;
        select.appendChild(opt);
    });
}


// ============= TRADING FUNCTIONS =============
function initTradeForm() {
    const tradeForm = document.getElementById('tradeForm');
    if (!tradeForm) return;
    
    tradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const symbol = document.getElementById('stockSymbol')?.value;
        const quantity = parseFloat(document.getElementById('quantity')?.value);
        const type = document.querySelector('input[name="type"]:checked')?.value;
        
        if (!symbol || !quantity || quantity <= 0 || !type) {
            showMessage('tradeMessage', 'Please fill all fields correctly', 'error');
            return;
        }
        
        const btn = tradeForm.querySelector('button[type="submit"]');
        const originalBtnText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Executing...';
        btn.disabled = true;
        
        try {
            const res = await fetch('/api/trade', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({symbol, quantity, type})
            });
            const data = await res.json();
            
            if (res.ok) {
                showMessage('tradeMessage', `✅ ${type} order executed!`, 'success');
                document.getElementById('quantity').value = '';
                
                if (data.new_balance) {
                    const balanceEl = document.getElementById('userBalance');
                    if (balanceEl) balanceEl.textContent = formatRupees(data.new_balance);
                }
                
                setTimeout(() => {
                    fetchPortfolio();
                    fetchStocks();
                }, 1000);
            } else {
                showMessage('tradeMessage', '❌ ' + (data.error || 'Trade failed'), 'error');
            }
        } catch (err) {
            console.error('Trade error:', err);
            showMessage('tradeMessage', '❌ Connection error', 'error');
        } finally {
            btn.innerHTML = originalBtnText;
            btn.disabled = false;
        }
    });
}

// Quick trade from stock card
function quickTrade(symbol, price) {
    const stockSelect = document.getElementById('stockSymbol');
    const quantityInput = document.getElementById('quantity');
    
    if (stockSelect && quantityInput) {
        stockSelect.value = symbol;
        quantityInput.focus();
        
        const balanceText = document.getElementById('userBalance')?.textContent || '₹10000';
        const balance = parseFloat(balanceText.replace(/[^0-9.]/g, '')) || 10000;
        quantityInput.value = (balance / price * 0.1).toFixed(2);
        
        // Scroll to trade form
        const tradeSection = document.getElementById('trade-section');
        if (tradeSection) {
            tradeSection.scrollIntoView({ behavior: 'smooth' });
        }
    } else {
        window.location.href = '/login/user';
    }
}


// ============= PORTFOLIO REALTIME SYSTEM =============
let holdingsData = [];
let updateInterval = null;

async function fetchPortfolio() {
    const portfolioTable = document.getElementById('holdingsTableBody') || document.getElementById('holdingsTable');
    if (!portfolioTable) return;
    
    try {
        const res = await fetch('/api/portfolio', { credentials: 'include' });
        
        if (res.status === 401) {
            window.location.href = '/login/user';
            return;
        }
        
        const data = await res.json();
        
        // Store holdings with currency info
        holdingsData = (data.holdings || []).map(h => ({
            ...h,
            currency: 'INR'
        }));
        
        renderHoldings(holdingsData);
        updateSummary({ ...data, holdings: holdingsData });
        
        // Start real-time price updates
        startRealTimeUpdates();
        
    } catch (error) {
        console.error('Error fetching portfolio:', error);
    }
}


// ============= START REALTIME POLLING =============
function startRealTimeUpdates() {
    if (updateInterval) clearInterval(updateInterval);
    
    updateInterval = setInterval(() => {
        updateStockPrices();
    }, 5000);
}


// ============= UPDATE STOCK PRICES (Real-time) =============
async function updateStockPrices() {
    if (!holdingsData.length) return;
    
    try {
        const res = await fetch('/api/stocks');
        if (!res.ok) return;
        const stocks = await res.json();
        
        const stockMap = {};
        stocks.forEach(stock => stockMap[stock.symbol] = stock);
        
        let hasChanges = false;
        
        holdingsData.forEach(holding => {
            const freshStock = stockMap[holding.symbol];
            if (!freshStock) return;
            
            const newPrice = freshStock.current_price;
            const oldPrice = lastPrices[holding.symbol] || holding.current_price;
            
            // Only update if price changed significantly
            if (Math.abs(oldPrice - newPrice) > 0.01) {
                holding.current_price = newPrice;
                holding.current_value = holding.quantity * newPrice;
                holding.change_percent = freshStock.change_percent;
                lastPrices[holding.symbol] = newPrice;
                hasChanges = true;
                
                updateHoldingRow(holding);
            }
        });
        
        if (hasChanges) {
            updateSummary({ holdings: holdingsData });
        }
        
    } catch (error) {
        console.error('Error updating prices:', error);
    }
}


// ============= UPDATE ROW WITH REALTIME P&L =============
function updateHoldingRow(holding) {
    const row = document.querySelector(`tr[data-symbol="${holding.symbol}"]`);
    if (!row) return;
    
    const priceCell = row.querySelector('.current-price-cell');
    const valueCell = row.querySelector('.market-value-cell');
    const plCell = row.querySelector('.pl-cell');
    
    const buyValue = holding.quantity * holding.avg_buy_price;
    const currentValue = holding.quantity * holding.current_price;
    const pl = currentValue - buyValue;
    
    // Update price with animation
    if (priceCell) {
        const arrow = holding.change_percent >= 0 ? '↑' : '↓';
        priceCell.classList.add('price-changing');
        priceCell.innerHTML = `<span class="${holding.change_percent >= 0 ? 'price-up' : 'price-down'}">${arrow} ${formatRupees(holding.current_price)}</span>`;
        setTimeout(() => priceCell.classList.remove('price-changing'), 1000);
    }
    
    // Update market value
    if (valueCell) {
        valueCell.textContent = formatRupees(currentValue);
    }
    
    // Update P&L with animation
    if (plCell) {
        const sign = pl >= 0 ? '+' : '';
        plCell.classList.add('price-changing');
        plCell.textContent = `${sign}${formatRupees(pl)}`;
        plCell.className = `pl-cell ${pl >= 0 ? 'price-up' : 'price-down'}`;
        setTimeout(() => plCell.classList.remove('price-changing'), 1000);
    }
}


// ============= RENDER HOLDINGS TABLE =============
function renderHoldings(holdings) {
    const tbody = document.getElementById('holdingsTableBody') || document.getElementById('holdingsTable');
    if (!tbody) return;
    
    if (!holdings || holdings.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p>No holdings yet</p>
                    <p style="font-size:0.9rem;margin-top:0.5rem;">Start trading to build your portfolio</p>
                    <a href="/explore" style="color:#2563eb;text-decoration:none;font-weight:500;margin-top:1rem;display:inline-block;">Explore Stocks →</a>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = holdings.map(h => {
        const buyValue = h.quantity * h.avg_buy_price;
        const currentValue = h.quantity * h.current_price;
        const pl = currentValue - buyValue;
        const sign = pl >= 0 ? '+' : '';
        const plClass = pl >= 0 ? 'price-up' : 'price-down';
        const priceClass = h.change_percent >= 0 ? 'price-up' : 'price-down';
        const arrow = h.change_percent >= 0 ? '↑' : '↓';
        
        return `
            <tr data-symbol="${h.symbol}">
                <td>
                    <div class="stock-info">
                        <div>
                            <div class="stock-symbol">${h.symbol}</div>
                            <div class="stock-name">${h.name}</div>
                        </div>
                    </div>
                </td>
                <td>${h.quantity.toLocaleString('en-IN')}</td>
                <td>${formatRupees(h.avg_buy_price)}</td>
                <td class="current-price-cell ${priceClass}">
                    ${arrow} ${formatRupees(h.current_price)}
                </td>
                <td class="market-value-cell">${formatRupees(currentValue)}</td>
                <td class="pl-cell ${plClass}">${sign}${formatRupees(pl)}</td>
                <td>
                    <div style="display:flex;gap:0.5rem;">
                        <a href="/stock/${h.symbol}" class="btn-action btn-view">
                            <i class="fas fa-chart-line"></i> View
                        </a>
                        <button class="btn-action btn-trade" onclick="tradeStock('${h.symbol}')">
                            <i class="fas fa-exchange-alt"></i> Trade
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}


// ============= PORTFOLIO SUMMARY =============
function updateSummary(data) {
    const totalValueEl = document.getElementById('totalValue');
    const totalPLEl = document.getElementById('totalPL');
    const stockCountEl = document.getElementById('stockCount');
    const bestPerformerEl = document.getElementById('bestPerformer');
    
    let totalValue = 0;
    let totalPL = 0;
    
    (data.holdings || []).forEach(h => {
        totalValue += h.current_value;
        totalPL += h.current_value - (h.quantity * h.avg_buy_price);
    });
    
    if (totalValueEl) {
        totalValueEl.textContent = formatRupees(totalValue);
    }
    
    if (totalPLEl) {
        const sign = totalPL >= 0 ? '+' : '';
        totalPLEl.textContent = `${sign}${formatRupees(Math.abs(totalPL))}`;
        totalPLEl.className = totalPL >= 0 ? 'profit' : 'loss';
    }
    
    if (stockCountEl) {
        stockCountEl.textContent = data.holdings?.length || 0;
    }
    
    if (bestPerformerEl && data.holdings && data.holdings.length > 0) {
        const best = data.holdings.reduce((prev, curr) => {
            const prevPL = prev.current_value - (prev.quantity * prev.avg_buy_price);
            const currPL = curr.current_value - (curr.quantity * curr.avg_buy_price);
            return currPL > prevPL ? curr : prev;
        });
        const bestPL = best.current_value - (best.quantity * best.avg_buy_price);
        const baseValue = best.quantity * best.avg_buy_price;
        const bestPLPercent = baseValue > 0 ? (bestPL / baseValue) * 100 : 0;
        const bestSign = bestPL >= 0 ? '+' : '';
        bestPerformerEl.textContent = `${best.symbol} (${bestSign}${bestPLPercent.toFixed(1)}%)`;
    }
}


// ============= UTILITY FUNCTIONS =============
function showMessage(elementId, text, type) {
    const el = document.getElementById(elementId);
    if (!el) {
        alert(text);
        return;
    }
    
    el.textContent = text;
    el.className = `message ${type}`;
    el.style.display = 'block';
    
    if (type === 'success') {
        setTimeout(() => {
            el.style.display = 'none';
        }, 3000);
    }
}

// Password strength checker
function checkPasswordStrength(password) {
    const bar = document.getElementById('passwordStrengthBar');
    if (!bar) return;
    
    if (password.length < 6) {
        bar.className = 'password-strength-bar';
    } else if (password.length < 10) {
        bar.className = 'password-strength-bar weak';
    } else if (password.length < 14) {
        bar.className = 'password-strength-bar medium';
    } else {
        bar.className = 'password-strength-bar strong';
    }
}

// Tab switching for auth pages
function showTab(tab) {
    document.querySelectorAll('.form-section').forEach(section => {
        section.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    if (tab === 'login') {
        document.getElementById('loginForm')?.classList.add('active');
        document.querySelectorAll('.tab-btn')[0]?.classList.add('active');
    } else {
        document.getElementById('signupForm')?.classList.add('active');
        document.querySelectorAll('.tab-btn')[1]?.classList.add('active');
    }
    
    ['message', 'signupMessage'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = '';
            el.className = 'message';
        }
    });
}

// Trade button handler for holdings
function tradeStock(symbol) {
    window.location.href = `/explore?buy=${symbol}`;
}


// ============= CLEANUP ON PAGE UNLOAD =============
window.addEventListener('beforeunload', () => {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
});
