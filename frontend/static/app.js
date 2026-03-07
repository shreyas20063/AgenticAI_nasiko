/**
 * Nasiko HR Platform - Frontend Application
 * Single-page app with login, dashboard, AI chat, recruitment pipeline,
 * interview calendar, onboarding, helpdesk, and compliance modules.
 */

(function () {
    'use strict';

    /* ============================================================
       SIMPLE MARKDOWN RENDERER (no external dependency)
       ============================================================ */
    function renderMarkdown(src) {
        if (!src) return '';
        let html = src
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
            return '<pre><code>' + code.trim() + '</code></pre>';
        });

        const lines = html.split('\n');
        const output = [];
        let inList = false;
        let listType = '';
        let inParagraph = false;

        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            const headerMatch = line.match(/^(#{1,4})\s+(.+)$/);
            if (headerMatch) {
                if (inParagraph) { output.push('</p>'); inParagraph = false; }
                if (inList) { output.push(listType === 'ul' ? '</ul>' : '</ol>'); inList = false; }
                const level = headerMatch[1].length;
                output.push('<h' + level + '>' + applyInline(headerMatch[2]) + '</h' + level + '>');
                continue;
            }
            if (/^[-*_]{3,}\s*$/.test(line)) {
                if (inParagraph) { output.push('</p>'); inParagraph = false; }
                if (inList) { output.push(listType === 'ul' ? '</ul>' : '</ol>'); inList = false; }
                output.push('<hr>');
                continue;
            }
            const ulMatch = line.match(/^(\s*)[-*+]\s+(.+)$/);
            if (ulMatch) {
                if (inParagraph) { output.push('</p>'); inParagraph = false; }
                if (!inList || listType !== 'ul') {
                    if (inList) output.push(listType === 'ul' ? '</ul>' : '</ol>');
                    output.push('<ul>');
                    inList = true;
                    listType = 'ul';
                }
                output.push('<li>' + applyInline(ulMatch[2]) + '</li>');
                continue;
            }
            const olMatch = line.match(/^(\s*)\d+\.\s+(.+)$/);
            if (olMatch) {
                if (inParagraph) { output.push('</p>'); inParagraph = false; }
                if (!inList || listType !== 'ol') {
                    if (inList) output.push(listType === 'ul' ? '</ul>' : '</ol>');
                    output.push('<ol>');
                    inList = true;
                    listType = 'ol';
                }
                output.push('<li>' + applyInline(olMatch[2]) + '</li>');
                continue;
            }
            if (inList && !/^\s/.test(line)) {
                output.push(listType === 'ul' ? '</ul>' : '</ol>');
                inList = false;
            }
            if (line.trim() === '') {
                if (inParagraph) { output.push('</p>'); inParagraph = false; }
                continue;
            }
            if (!inParagraph) {
                output.push('<p>');
                inParagraph = true;
            } else {
                output.push('<br>');
            }
            output.push(applyInline(line));
        }
        if (inParagraph) output.push('</p>');
        if (inList) output.push(listType === 'ul' ? '</ul>' : '</ol>');
        return output.join('\n');
    }

    function applyInline(text) {
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        text = text.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
        return text;
    }

    /* ============================================================
       STATE
       ============================================================ */
    const state = {
        token: localStorage.getItem('nasiko_token') || null,
        userId: localStorage.getItem('nasiko_user_id') || null,
        userRole: localStorage.getItem('nasiko_user_role') || null,
        userEmail: localStorage.getItem('nasiko_user_email') || null,
        tenantId: localStorage.getItem('nasiko_tenant_id') || null,
        conversationId: null,
        currentSection: 'dashboard',
        isChatLoading: false,
        loaded: { recruitment: false, onboarding: false, helpdesk: false, compliance: false },
        recruitmentView: 'table',
        // Cache data for filtering/pagination
        cache: {
            jobs: [],
            allCandidates: [],
            tickets: [],
            auditLogs: [],
            interviews: [],
        },
        filters: {
            recruitment: { search: '', status: '' },
            helpdesk: { search: '', priority: '', status: '' },
            compliance: { search: '', riskLevel: '' },
        },
        pagination: {
            recruitment: { page: 1, perPage: 25 },
            helpdesk: { page: 1, perPage: 25 },
            compliance: { page: 1, perPage: 25 },
        },
        charts: {},
    };

    /* ============================================================
       DOM REFS
       ============================================================ */
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        loginScreen: $('#login-screen'),
        appShell: $('#app-shell'),
        loginForm: $('#login-form'),
        loginEmail: $('#login-email'),
        loginPassword: $('#login-password'),
        loginError: $('#login-error'),
        loginBtn: $('#login-btn'),
        fillDemoBtn: $('#fill-demo-btn'),
        logoutBtn: $('#logout-btn'),
        userName: $('#user-name'),
        userRoleBadge: $('#user-role-badge'),
        healthDot: null,
        healthText: null,
        sidebarToggle: $('#sidebar-toggle'),
        sidebar: $('#sidebar'),
        sidebarLinks: $$('.sidebar-link'),
        sections: $$('.content-section'),
        chatMessages: $('#chat-messages'),
        chatForm: $('#chat-form'),
        chatInput: $('#chat-input'),
        chatSendBtn: $('#chat-send-btn'),
        metricCandidates: $('#metric-candidates'),
        metricTickets: $('#metric-tickets'),
        metricResolved: $('#metric-resolved'),
        metricCompliance: $('#metric-compliance'),
        toastContainer: $('#toast-container'),
        modalOverlay: $('#modal-overlay'),
    };

    /* ============================================================
       API HELPERS
       ============================================================ */
    const API_BASE = '';

    async function apiFetch(path, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        };
        if (state.token) {
            headers['Authorization'] = `Bearer ${state.token}`;
        }
        const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
        if (response.status === 401) {
            logout();
            throw new Error('Session expired. Please log in again.');
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Request failed (${response.status})`);
        }
        return response.json();
    }

    /* ============================================================
       TOAST NOTIFICATION SYSTEM
       ============================================================ */
    const TOAST_ICONS = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22,4 12,14.01 9,11.01"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    };

    function showToast(message, type = 'info', duration = 4000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${TOAST_ICONS[type] || TOAST_ICONS.info}</span>
            <span class="toast-body">${escapeHtml(message)}</span>
            <button class="toast-close" aria-label="Close">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        `;
        toast.querySelector('.toast-close').addEventListener('click', () => removeToast(toast));
        dom.toastContainer.appendChild(toast);
        if (duration > 0) {
            setTimeout(() => removeToast(toast), duration);
        }
        return toast;
    }

    function removeToast(toast) {
        if (!toast || !toast.parentElement) return;
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }

    /* ============================================================
       MODAL SYSTEM
       ============================================================ */
    function openModal(title, bodyHtml, options = {}) {
        const sizeClass = options.size === 'lg' ? 'modal-lg' : options.size === 'xl' ? 'modal-xl' : '';
        const footerHtml = options.footer || '';

        dom.modalOverlay.innerHTML = `
            <div class="modal ${sizeClass}">
                <div class="modal-header">
                    <h3>${escapeHtml(title)}</h3>
                    <button class="modal-close" aria-label="Close modal">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                <div class="modal-body">${bodyHtml}</div>
                ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}
            </div>
        `;

        dom.modalOverlay.hidden = false;
        dom.modalOverlay.classList.remove('closing');

        // Close handlers
        dom.modalOverlay.querySelector('.modal-close').addEventListener('click', closeModal);
        dom.modalOverlay.addEventListener('click', (e) => {
            if (e.target === dom.modalOverlay) closeModal();
        });

        // Run callback after modal is in DOM
        if (options.onOpen) {
            requestAnimationFrame(() => options.onOpen(dom.modalOverlay.querySelector('.modal')));
        }

        return dom.modalOverlay.querySelector('.modal');
    }

    function closeModal() {
        dom.modalOverlay.classList.add('closing');
        setTimeout(() => {
            dom.modalOverlay.hidden = true;
            dom.modalOverlay.innerHTML = '';
            dom.modalOverlay.classList.remove('closing');
        }, 200);
    }

    /* ============================================================
       SKELETON LOADERS
       ============================================================ */
    function skeletonMetrics(count = 4) {
        let html = '';
        for (let i = 0; i < count; i++) {
            html += '<div class="metric-card"><div class="skeleton skeleton-metric"></div></div>';
        }
        return html;
    }

    function skeletonRows(count = 5) {
        let html = '';
        for (let i = 0; i < count; i++) {
            html += '<div class="skeleton skeleton-row"></div>';
        }
        return html;
    }

    function skeletonCards(count = 3) {
        let html = '';
        for (let i = 0; i < count; i++) {
            html += '<div class="skeleton skeleton-card" style="margin-bottom:12px"></div>';
        }
        return html;
    }

    /* ============================================================
       TIME HELPERS
       ============================================================ */
    function fmtDate(isoStr) {
        if (!isoStr) return '\u2014';
        const d = new Date(isoStr);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function fmtTime(isoStr) {
        if (!isoStr) return '';
        const d = new Date(isoStr);
        return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    }

    function relativeTime(isoStr) {
        if (!isoStr) return '';
        const now = new Date();
        const then = new Date(isoStr);
        const diffMs = now - then;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHr = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHr / 24);

        if (diffSec < 60) return 'just now';
        if (diffMin < 60) return `${diffMin}m ago`;
        if (diffHr < 24) return `${diffHr}h ago`;
        if (diffDay < 7) return `${diffDay}d ago`;
        return fmtDate(isoStr);
    }

    function absoluteTime(isoStr) {
        if (!isoStr) return '';
        const d = new Date(isoStr);
        return d.toLocaleString('en-US', {
            month: 'long', day: 'numeric', year: 'numeric',
            hour: 'numeric', minute: '2-digit'
        });
    }

    /* ============================================================
       AUTH
       ============================================================ */
    async function login(email, password) {
        const data = await apiFetch('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
        state.token = data.access_token;
        state.userId = data.user_id;
        state.userRole = data.role;
        state.userEmail = email;
        state.tenantId = data.tenant_id;

        localStorage.setItem('nasiko_token', data.access_token);
        localStorage.setItem('nasiko_user_id', data.user_id);
        localStorage.setItem('nasiko_user_role', data.role);
        localStorage.setItem('nasiko_user_email', email);
        localStorage.setItem('nasiko_tenant_id', data.tenant_id);
    }

    function logout() {
        state.token = null;
        state.userId = null;
        state.userRole = null;
        state.userEmail = null;
        state.tenantId = null;
        state.conversationId = null;
        localStorage.removeItem('nasiko_token');
        localStorage.removeItem('nasiko_user_id');
        localStorage.removeItem('nasiko_user_role');
        localStorage.removeItem('nasiko_user_email');
        localStorage.removeItem('nasiko_tenant_id');
        showLogin();
    }

    /* ============================================================
       VIEW MANAGEMENT
       ============================================================ */
    function showLogin() {
        dom.loginScreen.hidden = false;
        dom.appShell.hidden = true;
        dom.loginError.hidden = true;
        dom.loginEmail.value = '';
        dom.loginPassword.value = '';
    }

    function showApp() {
        dom.loginScreen.hidden = true;
        dom.appShell.hidden = false;
        dom.userName.textContent = state.userEmail;
        dom.userRoleBadge.textContent = formatRole(state.userRole);
        dom.healthDot = $('.health-dot');
        dom.healthText = $('.health-text');
        initDarkMode();
        initNotificationCenter();
        wireHeaderButtons();
        loadDashboard();
        checkHealth();
        switchSection('dashboard');
    }

    function wireHeaderButtons() {
        // Global search button
        const searchBtn = $('#global-search-btn');
        if (searchBtn) searchBtn.addEventListener('click', openGlobalSearch);
        // Export buttons
        const expRecruitment = $('#btn-export-recruitment');
        if (expRecruitment) expRecruitment.addEventListener('click', exportCurrentTab);
        const expHelpdesk = $('#btn-export-helpdesk');
        if (expHelpdesk) expHelpdesk.addEventListener('click', exportCurrentTab);
        const expCompliance = $('#btn-export-compliance');
        if (expCompliance) expCompliance.addEventListener('click', exportCurrentTab);
        const expOnboarding = $('#btn-export-onboarding');
        if (expOnboarding) expOnboarding.addEventListener('click', () => {
            showToast('Onboarding export not yet available', 'info');
        });
        const reportBtn = $('#btn-generate-report');
        if (reportBtn) reportBtn.addEventListener('click', openComplianceReport);
        // New ticket button
        const newTicket = $('#btn-new-ticket');
        if (newTicket) newTicket.addEventListener('click', openCreateTicketModal);
        // User name click → settings
        const userNameEl = $('#user-name');
        if (userNameEl) {
            userNameEl.style.cursor = 'pointer';
            userNameEl.title = 'Click for settings';
            userNameEl.addEventListener('click', openUserSettings);
        }
    }

    function formatRole(role) {
        if (!role) return '';
        return role.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    }

    function switchSection(sectionName) {
        state.currentSection = sectionName;
        dom.sidebarLinks.forEach((link) => {
            link.classList.toggle('active', link.dataset.section === sectionName);
        });
        dom.sections.forEach((sec) => {
            sec.classList.toggle('active', sec.id === `section-${sectionName}`);
        });
        dom.sidebar.classList.remove('open');
        const overlay = $('.sidebar-overlay');
        if (overlay) overlay.classList.remove('visible');
        if (sectionName === 'chat') scrollChatToBottom();
        if (!state.loaded[sectionName]) {
            if (sectionName === 'recruitment') loadRecruitmentData();
            if (sectionName === 'onboarding') loadOnboardingData();
            if (sectionName === 'helpdesk') loadHelpdeskData();
            if (sectionName === 'compliance') loadComplianceData();
        }
    }

    /* ============================================================
       HEALTH CHECK
       ============================================================ */
    async function checkHealth() {
        try {
            await apiFetch('/api/admin/health');
            if (dom.healthDot) {
                dom.healthDot.className = 'health-dot healthy';
                dom.healthText.textContent = 'System Healthy';
            }
        } catch {
            if (dom.healthDot) {
                dom.healthDot.className = 'health-dot unhealthy';
                dom.healthText.textContent = 'Unhealthy';
            }
        }
    }

    /* ============================================================
       SEARCH & FILTER BAR BUILDER
       ============================================================ */
    function buildSearchBar(containerId, options = {}) {
        const container = $(containerId);
        if (!container) return;

        let html = `
            <div class="search-input-wrap">
                <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input type="text" placeholder="${options.placeholder || 'Search...'}" data-filter-search>
            </div>
        `;

        if (options.filters) {
            options.filters.forEach(f => {
                html += `<select class="filter-select" data-filter-key="${f.key}">`;
                html += `<option value="">${f.label}</option>`;
                f.options.forEach(o => {
                    html += `<option value="${o.value}">${o.label}</option>`;
                });
                html += '</select>';
            });
        }

        container.innerHTML = html;

        // Bind events
        const searchInput = container.querySelector('[data-filter-search]');
        if (searchInput && options.onFilter) {
            searchInput.addEventListener('input', () => options.onFilter());
        }
        container.querySelectorAll('[data-filter-key]').forEach(sel => {
            if (options.onFilter) {
                sel.addEventListener('change', () => options.onFilter());
            }
        });
    }

    function getFilterValues(containerId) {
        const container = $(containerId);
        if (!container) return { search: '' };
        const vals = { search: (container.querySelector('[data-filter-search]')?.value || '').toLowerCase() };
        container.querySelectorAll('[data-filter-key]').forEach(sel => {
            vals[sel.dataset.filterKey] = sel.value;
        });
        return vals;
    }

    /* ============================================================
       PAGINATION BUILDER
       ============================================================ */
    function renderPagination(containerId, totalItems, page, perPage, onPageChange) {
        const totalPages = Math.ceil(totalItems / perPage);
        if (totalPages <= 1) return '';

        const start = (page - 1) * perPage + 1;
        const end = Math.min(page * perPage, totalItems);

        let html = `<div class="pagination">
            <span class="pagination-info">Showing ${start}\u2013${end} of ${totalItems}</span>
            <div class="pagination-controls">
                <button class="pagination-btn" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>&laquo;</button>`;

        for (let i = 1; i <= totalPages && i <= 7; i++) {
            const p = totalPages <= 7 ? i :
                (i <= 3 ? i :
                    (i === 4 ? (page > 4 ? page : 4) :
                        (totalPages - (7 - i))));
            html += `<button class="pagination-btn ${p === page ? 'active' : ''}" data-page="${p}">${p}</button>`;
        }

        html += `<button class="pagination-btn" data-page="${page + 1}" ${page >= totalPages ? 'disabled' : ''}>&raquo;</button>
            </div>
        </div>`;

        // We'll append to the container
        const target = $(containerId);
        if (target) {
            // Remove existing pagination
            const existing = target.querySelector('.pagination');
            if (existing) existing.remove();

            target.insertAdjacentHTML('beforeend', html);
            target.querySelectorAll('.pagination-btn[data-page]').forEach(btn => {
                btn.addEventListener('click', () => {
                    const p = parseInt(btn.dataset.page);
                    if (p >= 1 && p <= totalPages) onPageChange(p);
                });
            });
        }
    }

    function paginate(items, page, perPage) {
        const start = (page - 1) * perPage;
        return items.slice(start, start + perPage);
    }

    /* ============================================================
       DASHBOARD
       ============================================================ */
    async function loadDashboard() {
        try {
            const data = await apiFetch('/api/admin/dashboard');
            const m = data.metrics || {};
            animateCounter(dom.metricCandidates, m.total_candidates ?? 0);
            animateCounter(dom.metricTickets, m.open_tickets ?? 0);
            animateCounter(dom.metricResolved, m.auto_resolved_tickets ?? 0);
            const total = (m.auto_resolved_tickets || 0) + (m.open_tickets || 0);
            const score = total > 0 ? Math.round(((m.auto_resolved_tickets || 0) / total) * 100) : 95;
            animateCounter(dom.metricCompliance, score, '%');
        } catch {
            dom.metricCandidates.textContent = '--';
            dom.metricTickets.textContent = '--';
            dom.metricResolved.textContent = '--';
            dom.metricCompliance.textContent = '--';
        }

        // Load dashboard widgets in parallel
        loadUpcomingInterviewsWidget();
        loadDashboardCharts();
    }

    function animateCounter(el, target, suffix = '') {
        if (!el) return;
        const duration = 600;
        const start = 0;
        const startTime = performance.now();

        function step(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + (target - start) * eased);
            el.textContent = current + suffix;
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    async function loadUpcomingInterviewsWidget() {
        const widget = $('#upcoming-interviews-widget');
        if (!widget) return;

        try {
            const data = await apiFetch('/api/interviews/upcoming?days=7');
            const badge = $('#interview-count-badge');
            if (badge && data.total_upcoming > 0) {
                badge.textContent = `${data.today} today`;
                badge.style.display = '';
            }

            if (!data.next_interviews || data.next_interviews.length === 0) {
                widget.innerHTML = '<div class="empty-state" style="padding:20px">No upcoming interviews</div>';
                return;
            }

            let html = '<div class="stagger-in">';
            data.next_interviews.forEach(i => {
                html += `
                    <div class="upcoming-interview-item">
                        <div class="upcoming-time">
                            <span class="time-value">${fmtTime(i.scheduled_at)}</span>
                            <span class="time-date">${fmtDate(i.scheduled_at)}</span>
                        </div>
                        <div class="upcoming-details">
                            <div class="name">${escapeHtml(i.candidate_name)}</div>
                            <div class="meta">${escapeHtml(i.interview_type)} interview</div>
                        </div>
                        <span class="interview-type-badge type-${i.interview_type}">${i.interview_type}</span>
                    </div>`;
            });
            html += '</div>';
            widget.innerHTML = html;
        } catch {
            widget.innerHTML = '<div class="empty-state" style="padding:20px">Could not load interviews</div>';
        }
    }

    async function loadDashboardCharts() {
        if (typeof Chart === 'undefined') return;

        // Pipeline funnel chart
        try {
            const jobs = await apiFetch('/api/recruitment/jobs');
            const allCands = [];
            for (const job of jobs) {
                try {
                    const cands = await apiFetch('/api/recruitment/candidates/' + job.id);
                    allCands.push(...cands);
                } catch { /* ignore */ }
            }
            const statusCounts = {};
            ['new', 'screened', 'shortlisted', 'interview', 'offered', 'hired', 'rejected'].forEach(s => statusCounts[s] = 0);
            allCands.forEach(c => { statusCounts[c.status] = (statusCounts[c.status] || 0) + 1; });

            const pipelineCtx = $('#chart-pipeline');
            if (pipelineCtx) {
                if (state.charts.pipeline) state.charts.pipeline.destroy();
                state.charts.pipeline = new Chart(pipelineCtx.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels: ['New', 'Screened', 'Shortlisted', 'Interview', 'Offered', 'Hired', 'Rejected'],
                        datasets: [{
                            label: 'Candidates',
                            data: [statusCounts.new, statusCounts.screened, statusCounts.shortlisted, statusCounts.interview, statusCounts.offered, statusCounts.hired, statusCounts.rejected],
                            backgroundColor: ['#818CF8', '#60A5FA', '#FBBF24', '#34D399', '#A78BFA', '#10B981', '#F87171'],
                            borderRadius: 6,
                            borderSkipped: false,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: '#F1F5F9' } },
                            x: { grid: { display: false } },
                        },
                    },
                });
            }
            // Save for recruitment tab
            state.cache.allCandidates = allCands;
            state.cache.jobs = jobs;
        } catch { /* ignore chart errors */ }

        // Tickets by category
        try {
            const tickets = await apiFetch('/api/helpdesk/tickets');
            const catCounts = {};
            tickets.forEach(t => {
                const cat = t.category || 'Other';
                catCounts[cat] = (catCounts[cat] || 0) + 1;
            });
            const ticketCtx = $('#chart-tickets');
            if (ticketCtx && Object.keys(catCounts).length > 0) {
                if (state.charts.tickets) state.charts.tickets.destroy();
                state.charts.tickets = new Chart(ticketCtx.getContext('2d'), {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(catCounts),
                        datasets: [{
                            data: Object.values(catCounts),
                            backgroundColor: ['#818CF8', '#60A5FA', '#FBBF24', '#34D399', '#F87171', '#A78BFA'],
                            borderWidth: 0,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom', labels: { padding: 12, usePointStyle: true, pointStyleWidth: 10 } },
                        },
                    },
                });
            }
            state.cache.tickets = tickets;
        } catch { /* ignore */ }

        // Activity chart (interviews per day next 7 days)
        try {
            const calData = await apiFetch('/api/interviews/calendar');
            const activityCtx = $('#chart-activity');
            if (activityCtx) {
                const dates = [];
                const counts = [];
                const now = new Date();
                for (let i = 0; i < 7; i++) {
                    const d = new Date(now);
                    d.setDate(d.getDate() + i);
                    const key = d.toISOString().split('T')[0];
                    dates.push(d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }));
                    counts.push((calData.calendar && calData.calendar[key]) ? calData.calendar[key].length : 0);
                }
                if (state.charts.activity) state.charts.activity.destroy();
                state.charts.activity = new Chart(activityCtx.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: dates,
                        datasets: [{
                            label: 'Interviews',
                            data: counts,
                            borderColor: '#4F46E5',
                            backgroundColor: 'rgba(79, 70, 229, 0.1)',
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: '#4F46E5',
                            pointRadius: 4,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: '#F1F5F9' } },
                            x: { grid: { display: false } },
                        },
                    },
                });
            }
        } catch { /* ignore */ }
    }

    /* ============================================================
       CHAT
       ============================================================ */
    function clearChatWelcome() {
        const welcome = dom.chatMessages.querySelector('.chat-welcome');
        if (welcome) welcome.remove();
    }

    function addChatMessage(role, text, meta = {}) {
        clearChatWelcome();

        const wrapper = document.createElement('div');
        wrapper.className = `chat-msg ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'chat-msg-avatar';
        avatar.textContent = role === 'user' ? 'U' : 'N';
        wrapper.appendChild(avatar);

        const body = document.createElement('div');
        body.className = 'chat-msg-body';

        // Meta line (agent badge, approval badge)
        if (role === 'assistant') {
            const metaEl = document.createElement('div');
            metaEl.className = 'chat-msg-meta';
            const nameSpan = document.createElement('span');
            nameSpan.textContent = 'Nasiko AI';
            metaEl.appendChild(nameSpan);

            if (meta.agentUsed) {
                const agentBadge = document.createElement('span');
                agentBadge.className = 'agent-badge';
                agentBadge.textContent = meta.agentUsed;
                metaEl.appendChild(agentBadge);
            }

            if (meta.requiresApproval) {
                const approvalBadge = document.createElement('span');
                approvalBadge.className = 'approval-badge';
                approvalBadge.textContent = 'Requires Approval';
                metaEl.appendChild(approvalBadge);
            }

            body.appendChild(metaEl);
        }

        // Message content
        const content = document.createElement('div');
        content.className = 'chat-msg-content';
        if (role === 'assistant') {
            content.innerHTML = renderMarkdown(text);
        } else {
            content.textContent = text;
        }
        body.appendChild(content);

        // Timestamp + Copy button (Feature 31)
        const timeStr = new Date().toISOString();
        const timeRow = document.createElement('div');
        timeRow.className = 'chat-msg-time';
        timeRow.innerHTML = `<span title="${absoluteTime(timeStr)}">${relativeTime(timeStr)}</span>`;
        if (role === 'assistant') {
            const copyBtn = document.createElement('button');
            copyBtn.className = 'chat-copy-btn';
            copyBtn.textContent = 'Copy';
            copyBtn.title = 'Copy message';
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(text).then(() => {
                    copyBtn.textContent = 'Copied!';
                    setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
                });
            });
            timeRow.appendChild(copyBtn);
        }
        body.appendChild(timeRow);

        // Actions taken
        if (meta.actionsTaken && meta.actionsTaken.length > 0) {
            const actionsContainer = document.createElement('div');
            actionsContainer.className = 'chat-actions';
            meta.actionsTaken.forEach((action) => {
                const item = document.createElement('div');
                item.className = 'action-item';
                item.innerHTML = `
                    <div class="action-item-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="4,17 10,11 4,5"/>
                            <line x1="12" y1="19" x2="20" y2="19"/>
                        </svg>
                    </div>
                    <div class="action-item-text">
                        <div class="action-item-tool">${escapeHtml(action.tool_name || action.action_type || 'Action')}</div>
                        <div class="action-item-detail">${escapeHtml(action.explanation || action.status || '')}</div>
                    </div>
                    <span class="action-item-status ${action.status || 'executed'}">${action.status || 'executed'}</span>
                `;
                actionsContainer.appendChild(item);
            });
            body.appendChild(actionsContainer);
        }

        // Approval bar
        if (meta.requiresApproval && meta.approvalAction && meta.conversationId) {
            const approvalBar = document.createElement('div');
            approvalBar.className = 'chat-approval-bar';
            approvalBar.innerHTML = `
                <p>This action requires your approval before execution.</p>
                <button class="btn btn-approve btn-sm" data-approve="true" data-conv="${escapeHtml(meta.conversationId)}">Approve</button>
                <button class="btn btn-deny btn-sm" data-approve="false" data-conv="${escapeHtml(meta.conversationId)}">Deny</button>
            `;
            approvalBar.querySelectorAll('button').forEach((btn) => {
                btn.addEventListener('click', () => handleApproval(btn.dataset.conv, btn.dataset.approve === 'true'));
            });
            body.appendChild(approvalBar);
        }

        wrapper.appendChild(body);
        dom.chatMessages.appendChild(wrapper);
        scrollChatToBottom();
    }

    function addTypingIndicator() {
        clearChatWelcome();
        const el = document.createElement('div');
        el.className = 'chat-msg assistant';
        el.id = 'typing-indicator';
        el.innerHTML = `
            <div class="chat-msg-avatar">N</div>
            <div class="chat-msg-body">
                <div class="chat-msg-content chat-typing">
                    <div class="typing-dots"><span></span><span></span><span></span></div>
                </div>
            </div>
        `;
        dom.chatMessages.appendChild(el);
        scrollChatToBottom();
    }

    function removeTypingIndicator() {
        const el = $('#typing-indicator');
        if (el) el.remove();
    }

    function scrollChatToBottom() {
        requestAnimationFrame(() => {
            dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
        });
    }

    async function sendChatMessage(message) {
        if (state.isChatLoading || !message.trim()) return;
        state.isChatLoading = true;
        dom.chatSendBtn.disabled = true;
        dom.chatInput.value = '';
        addChatMessage('user', message);
        addTypingIndicator();

        try {
            const payload = { message: message.trim() };
            if (state.conversationId) payload.conversation_id = state.conversationId;

            const data = await apiFetch('/api/chat/', {
                method: 'POST',
                body: JSON.stringify(payload),
            });

            removeTypingIndicator();
            state.conversationId = data.conversation_id;

            addChatMessage('assistant', data.message, {
                agentUsed: data.agent_used,
                actionsTaken: data.actions_taken,
                requiresApproval: data.requires_approval,
                approvalAction: data.approval_action,
                conversationId: data.conversation_id,
            });
        } catch (err) {
            removeTypingIndicator();
            addChatMessage('assistant', `Error: ${err.message}. Please try again.`);
            showToast(err.message, 'error');
        } finally {
            state.isChatLoading = false;
            updateSendButton();
        }
    }

    async function handleApproval(conversationId, approved) {
        try {
            const data = await apiFetch(`/api/chat/approve/${conversationId}?approved=${approved}`, {
                method: 'POST',
            });
            addChatMessage('assistant', data.message || (approved ? 'Action approved and executed.' : 'Action denied.'));
            showToast(approved ? 'Action approved successfully' : 'Action denied', approved ? 'success' : 'warning');
        } catch (err) {
            addChatMessage('assistant', `Approval error: ${err.message}`);
            showToast(`Approval failed: ${err.message}`, 'error');
        }
    }

    function updateSendButton() {
        const hasText = dom.chatInput.value.trim().length > 0;
        dom.chatSendBtn.disabled = !hasText || state.isChatLoading;
    }

    /* ============================================================
       CANDIDATE DETAIL MODAL
       ============================================================ */
    async function openCandidateDetail(candidateId) {
        openModal('Loading...', '<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>', { size: 'lg' });

        try {
            const data = await apiFetch(`/api/recruitment/candidate/${candidateId}`);
            const c = data;
            const score = c.screening_score;
            const scoreClass = score >= 80 ? 'high' : score >= 50 ? 'mid' : 'low';

            let bodyHtml = `
                <div class="candidate-profile">
                    <div class="profile-field">
                        <span class="profile-field-label">Full Name</span>
                        <span class="profile-field-value">${escapeHtml(c.full_name)}</span>
                    </div>
                    <div class="profile-field">
                        <span class="profile-field-label">Email</span>
                        <span class="profile-field-value">${escapeHtml(c.email)}</span>
                    </div>
                    <div class="profile-field">
                        <span class="profile-field-label">Status</span>
                        <span class="profile-field-value"><span class="badge badge-${c.status}">${c.status}</span></span>
                    </div>
                    <div class="profile-field">
                        <span class="profile-field-label">Experience</span>
                        <span class="profile-field-value">${c.years_experience != null ? c.years_experience + ' years' : '\u2014'}</span>
                    </div>
                    ${c.current_title ? `<div class="profile-field"><span class="profile-field-label">Current Title</span><span class="profile-field-value">${escapeHtml(c.current_title)}</span></div>` : ''}
                    ${c.current_company ? `<div class="profile-field"><span class="profile-field-label">Company</span><span class="profile-field-value">${escapeHtml(c.current_company)}</span></div>` : ''}
                    ${c.education_level ? `<div class="profile-field"><span class="profile-field-label">Education</span><span class="profile-field-value">${escapeHtml(c.education_level)}</span></div>` : ''}
                    ${c.location ? `<div class="profile-field"><span class="profile-field-label">Location</span><span class="profile-field-value">${escapeHtml(c.location)}</span></div>` : ''}
                </div>

                ${score != null ? `
                <div class="profile-section">
                    <h4>Screening Score</h4>
                    <div class="score-display">
                        <span class="score-number score-${scoreClass}">${score}</span>
                        <span class="score-label">${c.screening_explanation || 'AI screening score'}</span>
                    </div>
                </div>` : ''}

                ${c.skills && c.skills.length > 0 ? `
                <div class="profile-section">
                    <h4>Skills</h4>
                    <div class="skills-grid">
                        ${c.skills.map(s => `<span class="skill-badge">${escapeHtml(s.name)}${s.proficiency ? ` <span class="proficiency">${s.proficiency}y</span>` : ''}</span>`).join('')}
                    </div>
                </div>` : ''}

                ${c.interviews && c.interviews.length > 0 ? `
                <div class="profile-section">
                    <h4>Interview History</h4>
                    <div class="interview-list stagger-in">
                        ${c.interviews.map(iv => `
                            <div class="interview-item" style="cursor:default">
                                <div class="interview-time">
                                    <span class="time-value">${fmtTime(iv.scheduled_at)}</span>
                                    <span class="time-date">${fmtDate(iv.scheduled_at)}</span>
                                </div>
                                <div class="interview-info">
                                    <div class="candidate-name">${escapeHtml(iv.interview_type)} Interview</div>
                                    <div class="job-title">${(iv.interviewer_names || []).join(', ') || 'No interviewers assigned'}</div>
                                </div>
                                <span class="badge badge-${iv.status}">${iv.status}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>` : ''}
            `;

            // Resume tab with keyword highlighting (Feature 9)
            if (c.resume_text) {
                let highlightedResume = escapeHtml(c.resume_text);
                // Highlight job-required skills in resume
                const allSkills = (c.skills || []).map(s => s.name);
                allSkills.forEach(skill => {
                    const regex = new RegExp('(' + skill.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
                    highlightedResume = highlightedResume.replace(regex, '<mark style="background:#FEF08A;padding:1px 2px;border-radius:2px">$1</mark>');
                });
                bodyHtml += `
                <div class="profile-section">
                    <h4>Resume</h4>
                    <div style="max-height:300px;overflow-y:auto;font-size:0.8125rem;line-height:1.7;padding:12px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);white-space:pre-wrap">${highlightedResume}</div>
                </div>`;
            }

            // Interview feedback section (Feature 2)
            if (c.interviews && c.interviews.length > 0) {
                c.interviews.forEach(iv => {
                    if (iv.feedback && iv.feedback.length > 0) {
                        bodyHtml += `<div class="profile-section"><h4>Interview Feedback (${escapeHtml(iv.interview_type)})</h4>`;
                        const avgRating = iv.feedback.reduce((sum, f) => sum + (f.overall_rating || 0), 0) / iv.feedback.length;
                        bodyHtml += `<div style="margin-bottom:8px"><strong>Average Rating:</strong> <span class="score score-${avgRating >= 4 ? 'high' : avgRating >= 3 ? 'mid' : 'low'}">${avgRating.toFixed(1)}/5</span></div>`;
                        iv.feedback.forEach(f => {
                            bodyHtml += `<div style="padding:8px 12px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);margin-bottom:6px;font-size:0.8125rem">
                                <div style="display:flex;justify-content:space-between;margin-bottom:4px"><strong>${escapeHtml(f.interviewer_name || 'Interviewer')}</strong><span class="badge badge-${f.recommendation || 'pending'}">${f.recommendation || 'Pending'}</span></div>
                                ${f.strengths ? `<div style="color:var(--color-success)">+ ${escapeHtml(f.strengths)}</div>` : ''}
                                ${f.weaknesses ? `<div style="color:var(--color-error)">- ${escapeHtml(f.weaknesses)}</div>` : ''}
                            </div>`;
                        });
                        bodyHtml += '</div>';
                    }
                });
            }

            // Pipeline action buttons
            const VALID_TRANSITIONS = {
                'new': ['screened', 'rejected'],
                'screened': ['shortlisted', 'rejected'],
                'shortlisted': ['interview', 'rejected'],
                'interview': ['offered', 'rejected'],
                'offered': ['hired', 'rejected'],
                'rejected': [],
                'hired': [],
            };

            const nextSteps = VALID_TRANSITIONS[c.status] || [];
            if (nextSteps.length > 0 || c.email) {
                bodyHtml += '<div class="profile-section"><h4>Actions</h4><div class="pipeline-actions">';
                // Email button (Feature 28)
                if (c.email) {
                    bodyHtml += `<button class="btn-pipeline btn-pipeline-advance" data-action="email" data-email="${escapeHtml(c.email)}" data-name="${escapeHtml(c.full_name)}">Send Email</button>`;
                }
                nextSteps.forEach(step => {
                    if (step === 'rejected') {
                        bodyHtml += `<button class="btn-pipeline btn-pipeline-reject" data-action="reject" data-candidate="${c.id}" data-status="rejected">Reject</button>`;
                    } else if (step === 'interview') {
                        bodyHtml += `<button class="btn-pipeline btn-pipeline-interview" data-action="schedule" data-candidate="${c.id}">Schedule Interview</button>`;
                    } else {
                        const label = step.charAt(0).toUpperCase() + step.slice(1);
                        bodyHtml += `<button class="btn-pipeline btn-pipeline-advance" data-action="advance" data-candidate="${c.id}" data-status="${step}">Advance to ${label}</button>`;
                    }
                });
                bodyHtml += '</div></div>';
            }

            // Re-render modal with data
            closeModal();
            const modal = openModal(c.full_name, bodyHtml, {
                size: 'lg',
                onOpen: (modalEl) => {
                    // Bind pipeline action buttons
                    modalEl.querySelectorAll('[data-action="advance"], [data-action="reject"]').forEach(btn => {
                        btn.addEventListener('click', async () => {
                            try {
                                btn.disabled = true;
                                await apiFetch(`/api/recruitment/candidate/${btn.dataset.candidate}/status`, {
                                    method: 'PATCH',
                                    body: JSON.stringify({ new_status: btn.dataset.status }),
                                });
                                showToast(`Candidate status updated to "${btn.dataset.status}"`, 'success');
                                closeModal();
                                state.loaded.recruitment = false;
                                loadRecruitmentData();
                            } catch (err) {
                                showToast(`Failed: ${err.message}`, 'error');
                                btn.disabled = false;
                            }
                        });
                    });
                    modalEl.querySelectorAll('[data-action="schedule"]').forEach(btn => {
                        btn.addEventListener('click', () => {
                            closeModal();
                            openScheduleInterviewModal(btn.dataset.candidate, c.full_name);
                        });
                    });
                    modalEl.querySelectorAll('[data-action="email"]').forEach(btn => {
                        btn.addEventListener('click', () => {
                            closeModal();
                            openEmailComposer(btn.dataset.email, `Regarding your application - ${c.full_name}`, '');
                        });
                    });
                }
            });
        } catch (err) {
            closeModal();
            showToast(`Could not load candidate: ${err.message}`, 'error');
        }
    }

    /* ============================================================
       INTERVIEW SCHEDULING MODAL
       ============================================================ */
    function openScheduleInterviewModal(candidateId, candidateName) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const defaultDate = tomorrow.toISOString().split('T')[0];

        const bodyHtml = `
            <div class="schedule-form">
                <p style="margin-bottom:8px;color:var(--color-text-secondary)">Scheduling interview for <strong>${escapeHtml(candidateName)}</strong></p>
                <div class="form-row">
                    <div class="form-group">
                        <label>Date</label>
                        <input type="date" id="schedule-date" value="${defaultDate}" min="${defaultDate}">
                    </div>
                    <div class="form-group">
                        <label>Time</label>
                        <input type="time" id="schedule-time" value="10:00">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Duration</label>
                        <select id="schedule-duration">
                            <option value="30">30 minutes</option>
                            <option value="45">45 minutes</option>
                            <option value="60" selected>60 minutes</option>
                            <option value="90">90 minutes</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Type</label>
                        <select id="schedule-type">
                            <option value="video">Video Call</option>
                            <option value="phone">Phone Screen</option>
                            <option value="onsite">On-Site</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>Interviewers (comma-separated names)</label>
                    <input type="text" id="schedule-interviewers" placeholder="e.g. Sarah Johnson, Mike Chen">
                </div>
                <div class="form-group">
                    <label>Notes (optional)</label>
                    <textarea id="schedule-notes" placeholder="Any special instructions..."></textarea>
                </div>
            </div>
        `;

        const footerHtml = `
            <button class="btn btn-ghost" onclick="document.querySelector('.modal-close').click()">Cancel</button>
            <button class="btn btn-primary" id="schedule-confirm-btn">Schedule Interview</button>
        `;

        openModal('Schedule Interview', bodyHtml, {
            footer: footerHtml,
            onOpen: (modalEl) => {
                const confirmBtn = modalEl.querySelector('#schedule-confirm-btn');
                confirmBtn.addEventListener('click', async () => {
                    const date = modalEl.querySelector('#schedule-date').value;
                    const time = modalEl.querySelector('#schedule-time').value;
                    const duration = parseInt(modalEl.querySelector('#schedule-duration').value);
                    const type = modalEl.querySelector('#schedule-type').value;
                    const interviewers = modalEl.querySelector('#schedule-interviewers').value;
                    const notes = modalEl.querySelector('#schedule-notes').value;

                    if (!date || !time) {
                        showToast('Please select date and time', 'warning');
                        return;
                    }

                    const scheduledAt = new Date(`${date}T${time}:00`).toISOString();
                    const interviewerNames = interviewers ? interviewers.split(',').map(s => s.trim()).filter(Boolean) : [];

                    confirmBtn.disabled = true;
                    confirmBtn.textContent = 'Scheduling...';

                    try {
                        // We need job_id. Try to get it from cached data
                        let jobId = '';
                        const cachedCand = state.cache.allCandidates.find(c => c.id === candidateId);
                        if (cachedCand && cachedCand.job_id) jobId = cachedCand.job_id;
                        if (!jobId && state.cache.jobs.length > 0) jobId = state.cache.jobs[0].id;

                        const result = await apiFetch('/api/interviews/', {
                            method: 'POST',
                            body: JSON.stringify({
                                candidate_id: candidateId,
                                job_id: jobId,
                                scheduled_at: scheduledAt,
                                duration_minutes: duration,
                                interview_type: type,
                                interviewer_names: interviewerNames,
                                notes: notes || null,
                            }),
                        });

                        showToast(`Interview scheduled for ${candidateName}`, 'success');
                        closeModal();
                        state.loaded.recruitment = false;
                        loadRecruitmentData();
                    } catch (err) {
                        showToast(`Failed: ${err.message}`, 'error');
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = 'Schedule Interview';
                    }
                });
            }
        });
    }

    /* ============================================================
       INTERVIEW CALENDAR VIEW
       ============================================================ */
    async function loadInterviewCalendar() {
        const container = $('#interview-calendar-container');
        if (!container) return;

        container.innerHTML = skeletonCards(2);

        try {
            const data = await apiFetch('/api/interviews/calendar');
            const interviews = [];

            Object.entries(data.calendar || {}).forEach(([dateStr, items]) => {
                items.forEach(item => {
                    interviews.push({ ...item, dateKey: dateStr });
                });
            });

            state.cache.interviews = interviews;

            // Build list view (more practical than calendar grid for small datasets)
            let html = `
                <div class="calendar-nav">
                    <h3>Interview Schedule</h3>
                    <span class="badge badge-info">${data.total_interviews} total</span>
                </div>
            `;

            if (interviews.length === 0) {
                html += '<div class="empty-state">No interviews scheduled. Use the chat or candidate pipeline to schedule interviews.</div>';
            } else {
                // Group by date
                const grouped = {};
                interviews.forEach(i => {
                    if (!grouped[i.dateKey]) grouped[i.dateKey] = [];
                    grouped[i.dateKey].push(i);
                });

                html += '<div class="interview-list stagger-in">';
                Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).forEach(([dateStr, items]) => {
                    const d = new Date(dateStr + 'T00:00:00');
                    const isToday = new Date().toISOString().split('T')[0] === dateStr;
                    html += `<div style="font-size:0.8125rem;font-weight:700;color:var(--color-text-secondary);margin:16px 0 8px;text-transform:uppercase;letter-spacing:0.04em">${isToday ? 'Today' : d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</div>`;

                    items.forEach(i => {
                        html += `
                            <div class="interview-item">
                                <div class="interview-time">
                                    <span class="time-value">${i.time || fmtTime(i.scheduled_at)}</span>
                                    <span class="time-date">${i.duration_minutes}min</span>
                                </div>
                                <div class="interview-info">
                                    <div class="candidate-name">${escapeHtml(i.candidate_name)}</div>
                                    <div class="job-title">${(i.interviewer_names || []).join(', ') || 'No interviewers'}</div>
                                </div>
                                <span class="interview-type-badge type-${i.interview_type}">${i.interview_type}</span>
                                <span class="badge badge-${i.status}">${i.status}</span>
                            </div>`;
                    });
                });
                html += '</div>';
            }

            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="empty-state">Could not load calendar: ${err.message}</div>`;
        }
    }

    /* ============================================================
       KANBAN BOARD
       ============================================================ */
    async function loadKanbanBoard(jobId) {
        const board = $('#kanban-board');
        if (!board) return;

        board.innerHTML = skeletonCards(3);

        try {
            let pipelineData;
            if (jobId) {
                pipelineData = await apiFetch(`/api/recruitment/pipeline/${jobId}`);
            } else {
                // Aggregate all jobs
                pipelineData = { pipeline: {}, total: 0 };
                for (const job of state.cache.jobs) {
                    try {
                        const p = await apiFetch(`/api/recruitment/pipeline/${job.id}`);
                        Object.entries(p.pipeline || {}).forEach(([status, candidates]) => {
                            if (!pipelineData.pipeline[status]) pipelineData.pipeline[status] = [];
                            pipelineData.pipeline[status].push(...candidates);
                        });
                        pipelineData.total += p.total || 0;
                    } catch { /* ignore */ }
                }
            }

            const stages = ['new', 'screened', 'shortlisted', 'interview', 'offered', 'hired', 'rejected'];
            const stageColors = {
                new: '#818CF8', screened: '#60A5FA', shortlisted: '#FBBF24',
                interview: '#34D399', offered: '#A78BFA', hired: '#10B981', rejected: '#F87171'
            };

            // Pipeline analytics (Feature 11) - conversion rates
            let analyticsHtml = '<div class="pipeline-analytics">';
            const stageLabels = { new: 'New', screened: 'Screened', shortlisted: 'Shortlisted', interview: 'Interview', offered: 'Offered', hired: 'Hired' };
            for (let i = 0; i < stages.length - 2; i++) { // skip 'rejected' column
                const fromStage = stages[i];
                const toStage = stages[i + 1];
                if (toStage === 'rejected') continue;
                const fromCount = (pipelineData.pipeline[fromStage] || []).length;
                const toCount = (pipelineData.pipeline[toStage] || []).length;
                const rate = fromCount > 0 ? Math.round((toCount / fromCount) * 100) : 0;
                if (fromCount > 0) {
                    analyticsHtml += `<span class="conversion-rate" title="${stageLabels[fromStage] || fromStage} to ${stageLabels[toStage] || toStage}">${stageLabels[fromStage] || fromStage} <span style="opacity:0.5">&rarr;</span> ${rate}%</span>`;
                }
            }
            analyticsHtml += '</div>';

            let html = analyticsHtml;
            stages.forEach(stage => {
                const candidates = pipelineData.pipeline[stage] || [];
                html += `
                    <div class="kanban-column">
                        <div class="kanban-column-header">
                            <span class="kanban-column-title" style="color:${stageColors[stage]}">${stage.charAt(0).toUpperCase() + stage.slice(1)}</span>
                            <span class="kanban-column-count">${candidates.length}</span>
                        </div>
                        <div class="kanban-column-body">`;

                candidates.forEach(c => {
                    const score = c.screening_score;
                    const scoreClass = score >= 80 ? 'high' : score >= 50 ? 'mid' : 'low';
                    const topSkills = (c.skills || []).slice(0, 3);

                    html += `
                        <div class="kanban-card" data-candidate-id="${c.id}">
                            <div class="kanban-card-name">${escapeHtml(c.full_name)}</div>
                            <div class="kanban-card-meta">
                                ${c.years_experience != null ? c.years_experience + 'y exp' : ''}
                                ${c.current_title ? ' \u00B7 ' + escapeHtml(c.current_title) : ''}
                            </div>
                            ${topSkills.length > 0 ? `<div class="kanban-card-skills">${topSkills.map(s => `<span class="skill-tag">${escapeHtml(s.name)}</span>`).join('')}</div>` : ''}
                            ${score != null ? `<div class="kanban-card-score"><span class="score-${scoreClass}">${score}</span></div>` : ''}
                        </div>`;
                });

                html += '</div></div>';
            });

            board.innerHTML = html;

            // Bind click on kanban cards
            board.querySelectorAll('.kanban-card[data-candidate-id]').forEach(card => {
                card.addEventListener('click', () => {
                    openCandidateDetail(card.dataset.candidateId);
                });
            });
        } catch (err) {
            board.innerHTML = `<div class="empty-state">Could not load pipeline: ${err.message}</div>`;
        }
    }

    /* ============================================================
       TAB DATA LOADERS
       ============================================================ */
    const svgBriefcase = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 3h-8v4h8V3z"/></svg>';
    const svgPeople = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4-4v2"/><circle cx="9" cy="7" r="4"/></svg>';
    const svgCheck = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22,4 12,14.01 9,11.01"/><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/></svg>';
    const svgShield = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>';
    const svgAlert = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
    const svgClock = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/></svg>';
    const svgCalendar = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>';

    function makeMetricCard(icon, value, label, colorClass) {
        return `<div class="metric-card">
            <div class="metric-icon ${colorClass}">${icon}</div>
            <div class="metric-info">
                <span class="metric-value">${value}</span>
                <span class="metric-label">${label}</span>
            </div>
        </div>`;
    }

    /* --- Recruitment --- */
    async function loadRecruitmentData() {
        const statsEl = $('#recruitment-stats');
        const bodyEl = $('#recruitment-body');

        if (statsEl) statsEl.innerHTML = skeletonMetrics(3);
        if (bodyEl) bodyEl.innerHTML = skeletonRows(5);

        try {
            // Use cached data if available (from dashboard charts)
            let jobs = state.cache.jobs;
            let allCandidates = state.cache.allCandidates;

            if (!jobs || jobs.length === 0) {
                jobs = await apiFetch('/api/recruitment/jobs');
                state.cache.jobs = jobs;
            }

            if (!allCandidates || allCandidates.length === 0) {
                allCandidates = [];
                for (const job of jobs) {
                    try {
                        const cands = await apiFetch('/api/recruitment/candidates/' + job.id);
                        allCandidates.push(...cands);
                    } catch { /* ignore */ }
                }
                state.cache.allCandidates = allCandidates;
            }

            const jobsWithCandidates = jobs.map(j => ({
                ...j,
                candidates: allCandidates.filter(c => c.job_id === j.id || true),
            }));

            // Actually map candidates per job properly
            const candidatesByJob = {};
            for (const job of jobs) {
                try {
                    candidatesByJob[job.id] = await apiFetch('/api/recruitment/candidates/' + job.id);
                } catch { candidatesByJob[job.id] = []; }
            }

            const totalCandidates = allCandidates.length;
            const openJobs = jobs.filter(j => j.status === 'open').length;
            const interviewCount = allCandidates.filter(c => c.status === 'interview').length;

            // Stats
            if (statsEl) {
                statsEl.innerHTML =
                    makeMetricCard(svgBriefcase, openJobs, 'Open Positions', 'metric-icon-blue') +
                    makeMetricCard(svgPeople, totalCandidates, 'Total Candidates', 'metric-icon-indigo') +
                    makeMetricCard(svgCalendar, interviewCount, 'In Interview', 'metric-icon-green') +
                    makeMetricCard(svgCheck, jobs.length, 'Total Jobs', 'metric-icon-amber');
            }

            // Build search bar
            buildSearchBar('#recruitment-search-bar', {
                placeholder: 'Search candidates...',
                filters: [
                    { key: 'status', label: 'All Statuses', options: [
                        { value: 'new', label: 'New' }, { value: 'screened', label: 'Screened' },
                        { value: 'shortlisted', label: 'Shortlisted' }, { value: 'interview', label: 'Interview' },
                        { value: 'offered', label: 'Offered' }, { value: 'hired', label: 'Hired' },
                        { value: 'rejected', label: 'Rejected' },
                    ]},
                ],
                onFilter: () => renderRecruitmentTable(jobs, candidatesByJob),
            });

            renderRecruitmentTable(jobs, candidatesByJob);
            state.loaded.recruitment = true;
        } catch (e) {
            if (bodyEl) bodyEl.innerHTML = '<div class="empty-state">Could not load recruitment data.</div>';
        }
    }

    function renderRecruitmentTable(jobs, candidatesByJob) {
        const bodyEl = $('#recruitment-body');
        if (!bodyEl) return;

        const filters = getFilterValues('#recruitment-search-bar');

        if (jobs.length === 0) {
            bodyEl.innerHTML = '<div class="empty-state">No job openings found.</div>';
            return;
        }

        let html = '<table class="data-table"><thead><tr><th>Position</th><th>Department</th><th>Location</th><th>Candidates</th><th>Status</th><th></th></tr></thead><tbody>';
        jobs.forEach((j, idx) => {
            let candidates = candidatesByJob[j.id] || [];

            // Apply filters
            if (filters.search) {
                candidates = candidates.filter(c =>
                    (c.full_name || '').toLowerCase().includes(filters.search) ||
                    (c.current_title || '').toLowerCase().includes(filters.search) ||
                    (c.email || '').toLowerCase().includes(filters.search)
                );
            }
            if (filters.status) {
                candidates = candidates.filter(c => c.status === filters.status);
            }

            html += `<tr>
                <td class="cell-primary"><a href="#" class="job-title-link" data-job-idx="${idx}" style="color:var(--color-primary);text-decoration:none;font-weight:600" title="Click to edit">${escapeHtml(j.title)}</a></td>
                <td>${escapeHtml(j.department || '\u2014')}</td>
                <td>${escapeHtml(j.location || '\u2014')}</td>
                <td>${candidates.length}</td>
                <td><span class="badge badge-${j.status}">${j.status}</span></td>
                <td><button class="btn-expand" data-toggle="cand-row-${idx}">View</button></td>
            </tr>`;
            html += `<tr class="candidates-row" id="cand-row-${idx}"><td colspan="6"><div class="candidates-list stagger-in">`;

            if (candidates.length === 0) {
                html += '<div class="cell-secondary">No candidates match filters</div>';
            } else {
                candidates.forEach(c => {
                    const score = c.screening_score != null ? c.screening_score : null;
                    const scoreClass = score >= 80 ? 'high' : score >= 50 ? 'mid' : 'low';
                    const topSkills = (c.skills || []).slice(0, 3);

                    html += `<div class="candidate-card clickable" data-candidate-id="${c.id}">
                        <div class="candidate-card-header">
                            <input type="checkbox" class="bulk-select-checkbox" data-bulk-id="${c.id}" onclick="event.stopPropagation()" title="Select for bulk actions">
                            <span class="name">${escapeHtml(c.full_name || 'Candidate')}</span>
                            <span class="badge badge-${c.status}">${c.status}</span>
                        </div>
                        ${c.current_title ? `<div class="candidate-title">${escapeHtml(c.current_title)}${c.current_company ? ' @ ' + escapeHtml(c.current_company) : ''}</div>` : ''}
                        <div class="candidate-details">
                            ${c.years_experience != null ? `<span>&#128188; ${c.years_experience}y exp</span>` : ''}
                            ${c.education_level ? `<span>&#127891; ${escapeHtml(c.education_level)}</span>` : ''}
                            ${c.location ? `<span>&#128205; ${escapeHtml(c.location)}</span>` : ''}
                        </div>
                        ${topSkills.length ? `<div class="candidate-skills">${topSkills.map(s => `<span class="skill-tag">${escapeHtml(s.name)}</span>`).join('')}</div>` : ''}
                        <div class="candidate-footer">
                            ${score != null ? `<span class="score score-${scoreClass}">${score}</span>` : '<span class="score score-none">&#8212;</span>'}
                        </div>
                    </div>`;
                });
            }
            html += '</div></td></tr>';
        });
        html += '</tbody></table>';
        bodyEl.innerHTML = html;

        // Bind candidate card clicks
        bodyEl.querySelectorAll('.candidate-card.clickable[data-candidate-id]').forEach(card => {
            card.addEventListener('click', () => {
                openCandidateDetail(card.dataset.candidateId);
            });
        });

        // Bind expand buttons
        bodyEl.querySelectorAll('.btn-expand[data-toggle]').forEach(btn => {
            btn.addEventListener('click', () => {
                const row = document.getElementById(btn.dataset.toggle);
                if (row) row.classList.toggle('visible');
            });
        });

        // Job title links → editor (Feature 10)
        bodyEl.querySelectorAll('.job-title-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const job = jobs[parseInt(link.dataset.jobIdx)];
                if (job) openJobEditor(job);
            });
        });

        // Bulk selection (Feature 6)
        setupBulkActions(bodyEl);
    }

    function setupBulkActions(container) {
        // Remove existing bulk bar
        const existingBar = $('.bulk-action-bar');
        if (existingBar) existingBar.remove();

        container.querySelectorAll('.bulk-select-checkbox').forEach(cb => {
            cb.addEventListener('change', () => {
                const selected = container.querySelectorAll('.bulk-select-checkbox:checked');
                let bar = $('.bulk-action-bar');
                if (selected.length > 0) {
                    if (!bar) {
                        bar = document.createElement('div');
                        bar.className = 'bulk-action-bar';
                        bar.innerHTML = `
                            <span class="bulk-count"></span>
                            <button class="btn btn-sm btn-primary" id="bulk-compare-btn">Compare</button>
                            <button class="btn btn-sm btn-ghost" id="bulk-email-btn">Email Selected</button>
                            <button class="btn btn-sm btn-ghost" style="color:var(--color-error)" id="bulk-reject-btn">Reject All</button>
                            <button class="btn btn-sm btn-ghost" id="bulk-clear-btn">Clear</button>
                        `;
                        document.body.appendChild(bar);
                        bar.querySelector('#bulk-compare-btn').addEventListener('click', () => {
                            const ids = Array.from(container.querySelectorAll('.bulk-select-checkbox:checked')).map(c => c.dataset.bulkId);
                            openCandidateComparison(ids);
                        });
                        bar.querySelector('#bulk-email-btn').addEventListener('click', () => {
                            const ids = Array.from(container.querySelectorAll('.bulk-select-checkbox:checked')).map(c => c.dataset.bulkId);
                            const emails = ids.map(id => {
                                const cand = (state.cache.allCandidates || []).find(c => c.id === id);
                                return cand ? cand.email : null;
                            }).filter(Boolean);
                            openEmailComposer(emails.join(', '), 'Regarding your application', '');
                        });
                        bar.querySelector('#bulk-reject-btn').addEventListener('click', async () => {
                            const ids = Array.from(container.querySelectorAll('.bulk-select-checkbox:checked')).map(c => c.dataset.bulkId);
                            if (!confirm(`Reject ${ids.length} candidate(s)?`)) return;
                            let ok = 0;
                            for (const id of ids) {
                                try {
                                    await apiFetch(`/api/recruitment/candidate/${id}/status`, {
                                        method: 'PATCH', body: JSON.stringify({ new_status: 'rejected' }),
                                    });
                                    ok++;
                                } catch { /* continue */ }
                            }
                            showToast(`${ok} candidate(s) rejected`, ok > 0 ? 'success' : 'error');
                            bar.remove();
                            state.loaded.recruitment = false;
                            loadRecruitmentData();
                        });
                        bar.querySelector('#bulk-clear-btn').addEventListener('click', () => {
                            container.querySelectorAll('.bulk-select-checkbox:checked').forEach(c => c.checked = false);
                            bar.remove();
                        });
                    }
                    bar.querySelector('.bulk-count').textContent = `${selected.length} selected`;
                } else {
                    if (bar) bar.remove();
                }
            });
        });
    }

    /* --- Onboarding --- */
    async function loadOnboardingData() {
        const statsEl = $('#onboarding-stats');
        const bodyEl = $('#onboarding-body');

        if (statsEl) statsEl.innerHTML = skeletonMetrics(3);
        if (bodyEl) bodyEl.innerHTML = skeletonCards(3);

        try {
            const [plans, stats] = await Promise.all([
                apiFetch('/api/onboarding/plans'),
                apiFetch('/api/onboarding/stats'),
            ]);

            if (statsEl) {
                statsEl.innerHTML =
                    makeMetricCard(svgClock, stats.active, 'Active Plans', 'metric-icon-blue') +
                    makeMetricCard(svgCheck, stats.completed, 'Completed', 'metric-icon-green') +
                    makeMetricCard(svgPeople, stats.avg_progress + '%', 'Avg Progress', 'metric-icon-indigo');
            }

            if (plans.length === 0) {
                bodyEl.innerHTML = '<div class="empty-state">No onboarding plans found.</div>';
            } else {
                let html = '<div class="stagger-in">';
                plans.forEach(p => {
                    const fillClass = p.progress_pct >= 100 ? 'complete' : '';
                    // At-risk detection (Feature 22)
                    const isAtRisk = p.status === 'active' && p.target_completion &&
                        new Date(p.target_completion) < new Date(Date.now() + 7 * 86400000) && p.progress_pct < 70;
                    html += `<div class="onboarding-card">
                        <div class="onboarding-card-header">
                            <h4>${escapeHtml(p.employee_name)}</h4>
                            ${isAtRisk ? '<span class="badge badge-high" style="margin-right:4px">At Risk</span>' : ''}
                            <span class="badge badge-${p.status}">${p.status}</span>
                        </div>
                        <div class="onboarding-card-meta">
                            <span>${escapeHtml(p.department)}</span>
                            <span>${escapeHtml(p.template_name || 'Custom')}</span>
                            <span>Started ${fmtDate(p.started_at)}</span>
                        </div>
                        <div class="progress-row">
                            <div class="progress-bar"><div class="progress-bar-fill ${fillClass}" style="width:${p.progress_pct}%"></div></div>
                            <span class="progress-label">${p.progress_pct}%</span>
                        </div>
                        <ul class="task-list">`;
                    (p.tasks || []).forEach(t => {
                        const doneClass = t.is_completed ? 'done' : '';
                        const checkSvg = t.is_completed
                            ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20,6 9,17 4,12"/></svg>'
                            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" opacity="0.3"><circle cx="12" cy="12" r="10"/></svg>';
                        // Due day indicator
                        const dueDayLabel = t.due_day ? `Day ${t.due_day}` : '';
                        html += `<li class="task-item ${doneClass}" data-task-id="${t.id}" data-completed="${t.is_completed}" style="cursor:pointer" title="Click to ${t.is_completed ? 'reopen' : 'complete'}">
                            <span class="task-check">${checkSvg}</span>
                            <span class="task-title">${escapeHtml(t.title)}</span>
                            <span class="category-tag">${t.category || ''}</span>
                            ${dueDayLabel ? `<span class="due-day-label">${dueDayLabel}</span>` : ''}
                        </li>`;
                    });
                    html += '</ul></div>';
                });
                html += '</div>';
                bodyEl.innerHTML = html;

                // Bind task click handlers for interactive completion
                bodyEl.querySelectorAll('.task-item[data-task-id]').forEach(li => {
                    li.addEventListener('click', async () => {
                        const taskId = li.dataset.taskId;
                        const isCompleted = li.dataset.completed === 'true';
                        try {
                            li.style.opacity = '0.5';
                            const result = await apiFetch(`/api/onboarding/tasks/${taskId}/status`, {
                                method: 'PATCH',
                                body: JSON.stringify({ is_completed: !isCompleted }),
                            });
                            showToast(result.message || `Task ${!isCompleted ? 'completed' : 'reopened'}`, 'success');
                            state.loaded.onboarding = false;
                            loadOnboardingData();
                        } catch (err) {
                            showToast(`Failed: ${err.message}`, 'error');
                            li.style.opacity = '1';
                        }
                    });
                });
            }
            state.loaded.onboarding = true;
        } catch (e) {
            bodyEl.innerHTML = '<div class="empty-state">Could not load onboarding data.</div>';
        }
    }

    /* --- Helpdesk --- */
    async function loadHelpdeskData() {
        const statsEl = $('#helpdesk-stats');
        const bodyEl = $('#helpdesk-body');

        if (statsEl) statsEl.innerHTML = skeletonMetrics(4);
        if (bodyEl) bodyEl.innerHTML = skeletonRows(5);

        try {
            const [tickets, stats] = await Promise.all([
                apiFetch('/api/helpdesk/tickets'),
                apiFetch('/api/helpdesk/stats'),
            ]);

            state.cache.tickets = tickets;

            if (statsEl) {
                statsEl.innerHTML =
                    makeMetricCard(svgAlert, stats.open, 'Open', 'metric-icon-blue') +
                    makeMetricCard(svgClock, stats.in_progress, 'In Progress', 'metric-icon-amber') +
                    makeMetricCard(svgCheck, stats.resolved, 'Resolved', 'metric-icon-green') +
                    makeMetricCard(svgPeople, stats.auto_resolved, 'Auto-Resolved', 'metric-icon-indigo');
            }

            // Build search bar
            buildSearchBar('#helpdesk-search-bar', {
                placeholder: 'Search tickets...',
                filters: [
                    { key: 'priority', label: 'All Priorities', options: [
                        { value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' },
                        { value: 'high', label: 'High' }, { value: 'urgent', label: 'Urgent' },
                    ]},
                    { key: 'status', label: 'All Statuses', options: [
                        { value: 'open', label: 'Open' }, { value: 'in_progress', label: 'In Progress' },
                        { value: 'waiting', label: 'Waiting' }, { value: 'resolved', label: 'Resolved' },
                    ]},
                ],
                onFilter: () => renderHelpdeskTable(),
            });

            renderHelpdeskTable();
            state.loaded.helpdesk = true;
        } catch (e) {
            if (bodyEl) bodyEl.innerHTML = '<div class="empty-state">Could not load ticket data.</div>';
        }
    }

    function renderHelpdeskTable() {
        const bodyEl = $('#helpdesk-body');
        if (!bodyEl) return;

        const filters = getFilterValues('#helpdesk-search-bar');
        let tickets = state.cache.tickets || [];

        // Apply filters
        if (filters.search) {
            tickets = tickets.filter(t =>
                (t.subject || '').toLowerCase().includes(filters.search) ||
                (t.requester_name || '').toLowerCase().includes(filters.search) ||
                (t.category || '').toLowerCase().includes(filters.search)
            );
        }
        if (filters.priority) tickets = tickets.filter(t => t.priority === filters.priority);
        if (filters.status) tickets = tickets.filter(t => t.status === filters.status);

        // Paginate
        const pg = state.pagination.helpdesk;
        const pageItems = paginate(tickets, pg.page, pg.perPage);

        if (tickets.length === 0) {
            bodyEl.innerHTML = '<div class="empty-state">No tickets match your filters.</div>';
            return;
        }

        let html = '<table class="data-table clickable"><thead><tr><th>Subject</th><th>Category</th><th>Requester</th><th>Priority</th><th>Status</th><th>SLA</th><th>Created</th></tr></thead><tbody>';
        pageItems.forEach(t => {
            const sla = calcSLA(t);
            html += `<tr data-ticket-id="${t.id}">
                <td class="cell-primary">${escapeHtml(t.subject)}</td>
                <td><span class="category-tag">${t.category || '\u2014'}</span></td>
                <td>${escapeHtml(t.requester_name)}</td>
                <td><span class="priority-dot p-${t.priority}">${t.priority}</span></td>
                <td><span class="badge badge-${t.status}">${t.status.replace('_', ' ')}</span></td>
                <td>${t.status === 'resolved' || t.status === 'closed' ? '<span class="sla-badge sla-green">Done</span>' : `<span class="sla-badge sla-${sla.color}">${sla.label}</span>`}</td>
                <td class="cell-secondary">${fmtDate(t.created_at)}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        bodyEl.innerHTML = html;

        // Pagination
        renderPagination('#helpdesk-body', tickets.length, pg.page, pg.perPage, (newPage) => {
            state.pagination.helpdesk.page = newPage;
            renderHelpdeskTable();
        });

        // Click on ticket row for detail
        bodyEl.querySelectorAll('tr[data-ticket-id]').forEach(row => {
            row.addEventListener('click', () => openTicketDetail(row.dataset.ticketId));
        });
    }

    async function openTicketDetail(ticketId) {
        // Fetch full ticket detail with messages from API
        let ticket;
        try {
            ticket = await apiFetch(`/api/helpdesk/tickets/${ticketId}`);
        } catch (e) {
            // Fallback to cache
            ticket = (state.cache.tickets || []).find(t => t.id === ticketId);
        }
        if (!ticket) { showToast('Ticket not found', 'error'); return; }

        // SLA calculation
        const created = new Date(ticket.created_at);
        const now = new Date();
        const hoursElapsed = Math.round((now - created) / 36e5);
        const slaMap = { urgent: 4, high: 24, medium: 48, low: 72 };
        const slaHours = slaMap[ticket.priority] || 48;
        const slaPct = Math.min(100, Math.round((hoursElapsed / slaHours) * 100));
        const slaClass = slaPct >= 100 ? 'sla-overdue' : slaPct >= 75 ? 'sla-warning' : 'sla-ok';
        const slaLabel = slaPct >= 100 ? 'OVERDUE' : `${slaHours - hoursElapsed}h remaining`;

        // Resolution time
        let resolutionTime = '';
        if (ticket.resolved_at) {
            const resolved = new Date(ticket.resolved_at);
            const diffH = Math.round((resolved - created) / 36e5);
            resolutionTime = diffH < 24 ? `${diffH} hours` : `${Math.round(diffH / 24)} days`;
        }

        // Messages thread
        const messages = ticket.messages || [];
        let threadHtml = '';
        if (messages.length > 0) {
            threadHtml = '<div class="profile-section"><h4>Conversation Thread</h4><div class="ticket-thread">';
            messages.forEach(m => {
                const isStaff = m.sender_name !== ticket.requester_name;
                threadHtml += `<div class="ticket-message ${isStaff ? 'staff' : 'requester'}">
                    <div class="ticket-message-header">
                        <span class="author">${escapeHtml(m.sender_name || 'System')}</span>
                        <span class="msg-time">${relativeTime(m.created_at)}</span>
                    </div>
                    <div class="msg-content">${escapeHtml(m.content)}</div>
                </div>`;
            });
            threadHtml += '</div></div>';
        }

        let bodyHtml = `
            <div class="ticket-detail-header">
                <span class="badge badge-${ticket.status}">${(ticket.status || '').replace('_', ' ')}</span>
                <span class="priority-dot p-${ticket.priority}">${ticket.priority} priority</span>
                <span class="sla-badge ${slaClass}" title="SLA: ${slaHours}h">${slaLabel}</span>
                ${resolutionTime ? `<span class="resolution-time">Resolved in ${resolutionTime}</span>` : ''}
            </div>
            <div class="candidate-profile">
                <div class="profile-field"><span class="profile-field-label">Requester</span><span class="profile-field-value">${escapeHtml(ticket.requester_name)}</span></div>
                <div class="profile-field"><span class="profile-field-label">Category</span><span class="profile-field-value">${escapeHtml(ticket.category || 'Uncategorized')}</span></div>
                <div class="profile-field"><span class="profile-field-label">Created</span><span class="profile-field-value">${absoluteTime(ticket.created_at)}</span></div>
                <div class="profile-field"><span class="profile-field-label">Assigned To</span><span class="profile-field-value">${escapeHtml(ticket.assigned_to_name || 'Unassigned')}</span></div>
            </div>
            ${threadHtml}
            <!-- Status Actions -->
            <div class="profile-section">
                <h4>Actions</h4>
                <div class="ticket-actions">
                    ${ticket.status !== 'in_progress' ? `<button class="btn btn-sm btn-primary" data-ticket-action="in_progress">Start Working</button>` : ''}
                    ${ticket.status !== 'resolved' ? `<button class="btn btn-sm btn-success" data-ticket-action="resolved">Resolve</button>` : ''}
                    ${ticket.status !== 'closed' ? `<button class="btn btn-sm btn-secondary" data-ticket-action="closed">Close</button>` : ''}
                    ${ticket.status === 'resolved' || ticket.status === 'closed' ? `<button class="btn btn-sm btn-outline" data-ticket-action="open">Reopen</button>` : ''}
                    <button class="btn btn-sm btn-ghost" data-ticket-email="${escapeHtml(ticket.requester_email || '')}" data-requester="${escapeHtml(ticket.requester_name || '')}">Email Requester</button>
                    <select class="priority-select" data-ticket-priority>
                        <option value="">Change Priority</option>
                        ${['low','medium','high','urgent'].map(p => `<option value="${p}" ${p === ticket.priority ? 'selected' : ''}>${p}</option>`).join('')}
                    </select>
                </div>
            </div>
            <!-- Quick Response Templates -->
            <div class="profile-section">
                <h4>Reply</h4>
                <div class="ticket-templates">
                    <button class="btn btn-xs btn-outline" data-template="Looking into this issue. Will update you shortly.">Looking into it</button>
                    <button class="btn btn-xs btn-outline" data-template="This has been escalated to the relevant team.">Escalated</button>
                    <button class="btn btn-xs btn-outline" data-template="This issue has been resolved. Please let us know if you need further assistance.">Resolved</button>
                </div>
                <textarea class="ticket-reply-input" placeholder="Type your reply..." rows="3"></textarea>
                <button class="btn btn-primary btn-sm" id="ticket-send-reply">Send Reply</button>
            </div>
        `;

        openModal(ticket.subject, bodyHtml, {
            size: 'lg',
            onOpen: (modalEl) => {
                // Status action buttons
                modalEl.querySelectorAll('[data-ticket-action]').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const newStatus = btn.dataset.ticketAction;
                        try {
                            btn.disabled = true;
                            await apiFetch(`/api/helpdesk/tickets/${ticketId}/status`, {
                                method: 'PATCH', body: JSON.stringify({ status: newStatus }),
                            });
                            showToast(`Ticket status updated to "${newStatus}"`, 'success');
                            closeModal();
                            state.loaded.helpdesk = false;
                            loadHelpdeskData();
                        } catch (err) {
                            showToast(`Failed: ${err.message}`, 'error');
                            btn.disabled = false;
                        }
                    });
                });

                // Email requester button
                const emailBtn = modalEl.querySelector('[data-ticket-email]');
                if (emailBtn) {
                    emailBtn.addEventListener('click', () => {
                        const email = emailBtn.dataset.ticketEmail;
                        const name = emailBtn.dataset.requester;
                        closeModal();
                        openEmailComposer(email, `Update: ${ticket.subject}`, '');
                    });
                }

                // Priority change
                const prioritySel = modalEl.querySelector('[data-ticket-priority]');
                if (prioritySel) {
                    prioritySel.addEventListener('change', async () => {
                        const newPriority = prioritySel.value;
                        if (!newPriority || newPriority === ticket.priority) return;
                        try {
                            await apiFetch(`/api/helpdesk/tickets/${ticketId}/status`, {
                                method: 'PATCH', body: JSON.stringify({ priority: newPriority }),
                            });
                            showToast(`Priority changed to "${newPriority}"`, 'success');
                        } catch (err) {
                            showToast(`Failed: ${err.message}`, 'error');
                        }
                    });
                }

                // Template buttons
                modalEl.querySelectorAll('[data-template]').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const textarea = modalEl.querySelector('.ticket-reply-input');
                        if (textarea) textarea.value = btn.dataset.template;
                    });
                });

                // Send reply
                const replyBtn = modalEl.querySelector('#ticket-send-reply');
                if (replyBtn) {
                    replyBtn.addEventListener('click', async () => {
                        const textarea = modalEl.querySelector('.ticket-reply-input');
                        const msg = textarea?.value?.trim();
                        if (!msg) { showToast('Please enter a reply', 'warning'); return; }
                        try {
                            replyBtn.disabled = true;
                            replyBtn.textContent = 'Sending...';
                            await apiFetch(`/api/helpdesk/tickets/${ticketId}/respond`, {
                                method: 'POST', body: JSON.stringify({ message: msg }),
                            });
                            showToast('Reply sent successfully', 'success');
                            closeModal();
                            openTicketDetail(ticketId); // Refresh to show new message
                        } catch (err) {
                            showToast(`Failed: ${err.message}`, 'error');
                            replyBtn.disabled = false;
                            replyBtn.textContent = 'Send Reply';
                        }
                    });
                }
            }
        });
    }

    /* --- Compliance --- */
    async function loadComplianceData() {
        const statsEl = $('#compliance-stats');
        const bodyEl = $('#compliance-body');

        if (statsEl) statsEl.innerHTML = skeletonMetrics(4);
        if (bodyEl) bodyEl.innerHTML = skeletonRows(5);

        try {
            const [metrics, logs] = await Promise.all([
                apiFetch('/api/compliance/metrics'),
                apiFetch('/api/compliance/audit-logs'),
            ]);

            state.cache.auditLogs = logs;

            if (statsEl) {
                statsEl.innerHTML =
                    makeMetricCard(svgShield, metrics.compliance_score + '%', 'Compliance Score', 'metric-icon-green') +
                    makeMetricCard(svgCheck, metrics.total_actions, 'Total Actions', 'metric-icon-blue') +
                    makeMetricCard(svgAlert, metrics.denied_actions, 'Denied', 'metric-icon-amber') +
                    makeMetricCard(svgAlert, metrics.high_risk_actions, 'High Risk', 'metric-icon-indigo');
            }

            // Build search bar
            buildSearchBar('#compliance-search-bar', {
                placeholder: 'Search audit logs...',
                filters: [
                    { key: 'riskLevel', label: 'All Risk Levels', options: [
                        { value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' }, { value: 'high', label: 'High' },
                    ]},
                ],
                onFilter: () => renderComplianceTable(),
            });

            renderComplianceTable();
            state.loaded.compliance = true;
        } catch (e) {
            if (bodyEl) bodyEl.innerHTML = '<div class="empty-state">Could not load compliance data.</div>';
        }
    }

    function renderComplianceTable() {
        const bodyEl = $('#compliance-body');
        if (!bodyEl) return;

        const filters = getFilterValues('#compliance-search-bar');
        let logs = state.cache.auditLogs || [];

        // Apply filters
        if (filters.search) {
            logs = logs.filter(l =>
                (l.action || '').toLowerCase().includes(filters.search) ||
                (l.agent || '').toLowerCase().includes(filters.search) ||
                (l.resource_type || '').toLowerCase().includes(filters.search)
            );
        }
        if (filters.riskLevel) logs = logs.filter(l => l.risk_level === filters.riskLevel);

        const pg = state.pagination.compliance;
        const pageItems = paginate(logs, pg.page, pg.perPage);

        if (logs.length === 0) {
            bodyEl.innerHTML = '<div class="empty-state">No audit logs match your filters.</div>';
            return;
        }

        let html = '<table class="data-table clickable"><thead><tr><th>Timestamp</th><th>Action</th><th>Agent</th><th>Role</th><th>Resource</th><th>Status</th><th>Risk</th></tr></thead><tbody>';
        pageItems.forEach((l, idx) => {
            html += `<tr data-audit-idx="${idx}" style="cursor:pointer">
                <td class="cell-secondary">${fmtDate(l.timestamp)}</td>
                <td class="cell-primary">${escapeHtml(l.action || '\u2014')}</td>
                <td>${escapeHtml(l.agent || '\u2014')}</td>
                <td>${escapeHtml(l.user_role || '\u2014')}</td>
                <td><span class="category-tag">${l.resource_type || '\u2014'}</span></td>
                <td><span class="badge badge-${l.status}">${l.status || '\u2014'}</span></td>
                <td><span class="badge badge-${l.risk_level}">${l.risk_level || '\u2014'}</span></td>
            </tr>`;
        });
        html += '</tbody></table>';
        bodyEl.innerHTML = html;

        // Bind audit log row click → detail modal
        bodyEl.querySelectorAll('tr[data-audit-idx]').forEach(row => {
            row.addEventListener('click', () => {
                const entry = pageItems[parseInt(row.dataset.auditIdx)];
                if (entry) openAuditLogDetail(entry);
            });
        });

        // Pagination
        renderPagination('#compliance-body', logs.length, pg.page, pg.perPage, (newPage) => {
            state.pagination.compliance.page = newPage;
            renderComplianceTable();
        });
    }

    /* ============================================================
       HELPERS
       ============================================================ */
    function escapeHtml(str) {
        if (!str) return '';
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(str).replace(/[&<>"']/g, (c) => map[c]);
    }

    /* SLA calculation (Feature 19) */
    function calcSLA(ticket) {
        if (!ticket.created_at) return { label: '--', color: 'green' };
        const slaHours = { low: 72, medium: 48, high: 24, urgent: 4 };
        const maxH = slaHours[ticket.priority] || 48;
        const elapsed = (Date.now() - new Date(ticket.created_at).getTime()) / 3600000;
        const pct = elapsed / maxH;
        const remaining = Math.max(0, maxH - elapsed);
        const label = remaining < 1 ? `${Math.round(remaining * 60)}m` : `${Math.round(remaining)}h`;
        if (pct >= 1) return { label: 'Overdue', color: 'red' };
        if (pct >= 0.75) return { label: label + ' left', color: 'yellow' };
        return { label: label + ' left', color: 'green' };
    }

    /* ============================================================
       EVENT BINDINGS
       ============================================================ */
    function bindEvents() {
        // Login form
        dom.loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            dom.loginError.hidden = true;
            const email = dom.loginEmail.value.trim();
            const password = dom.loginPassword.value;
            if (!email || !password) return;

            dom.loginBtn.disabled = true;
            dom.loginBtn.querySelector('.btn-text').hidden = true;
            dom.loginBtn.querySelector('.btn-spinner').hidden = false;

            try {
                await login(email, password);
                showApp();
                showToast('Welcome back!', 'success');
            } catch (err) {
                dom.loginError.textContent = err.message;
                dom.loginError.hidden = false;
            } finally {
                dom.loginBtn.disabled = false;
                dom.loginBtn.querySelector('.btn-text').hidden = false;
                dom.loginBtn.querySelector('.btn-spinner').hidden = true;
            }
        });

        // Fill demo credentials
        dom.fillDemoBtn.addEventListener('click', () => {
            dom.loginEmail.value = 'admin@acme.demo';
            dom.loginPassword.value = 'demo12345';
            dom.loginEmail.focus();
        });

        // Logout
        dom.logoutBtn.addEventListener('click', () => {
            logout();
            showToast('Logged out successfully', 'info');
        });

        // Sidebar navigation
        dom.sidebarLinks.forEach((link) => {
            link.addEventListener('click', () => {
                switchSection(link.dataset.section);
            });
        });

        // Mobile sidebar toggle
        dom.sidebarToggle.addEventListener('click', () => {
            const isOpen = dom.sidebar.classList.toggle('open');
            let overlay = $('.sidebar-overlay');
            if (isOpen && !overlay) {
                overlay = document.createElement('div');
                overlay.className = 'sidebar-overlay visible';
                overlay.addEventListener('click', () => {
                    dom.sidebar.classList.remove('open');
                    overlay.classList.remove('visible');
                });
                document.body.appendChild(overlay);
            } else if (overlay) {
                overlay.classList.toggle('visible', isOpen);
            }
        });

        // Chat form submit
        dom.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            sendChatMessage(dom.chatInput.value);
        });

        dom.chatInput.addEventListener('input', updateSendButton);

        // Suggestion chips
        document.addEventListener('click', (e) => {
            const chip = e.target.closest('.suggestion-chip');
            if (chip) {
                const msg = chip.dataset.message;
                if (msg) {
                    switchSection('chat');
                    sendChatMessage(msg);
                }
            }
        });

        // Quick action cards
        document.addEventListener('click', (e) => {
            const actionCard = e.target.closest('[data-action]');
            if (!actionCard) return;
            const action = actionCard.dataset.action;
            if (action === 'goto-chat') { switchSection('chat'); return; }
            const actionSections = {
                'chat-recruit': 'recruitment',
                'chat-onboard': 'onboarding',
                'chat-helpdesk': 'helpdesk',
                'chat-compliance': 'compliance',
            };
            const targetSection = actionSections[action];
            if (targetSection) switchSection(targetSection);
        });

        // Recruitment view toggle (table / pipeline / calendar)
        const viewToggle = $('#recruitment-view-toggle');
        if (viewToggle) {
            viewToggle.querySelectorAll('.view-toggle-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    viewToggle.querySelectorAll('.view-toggle-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    const view = btn.dataset.view;
                    state.recruitmentView = view;

                    // Show/hide views
                    const tableView = $('#recruitment-table-view');
                    const pipelineView = $('#recruitment-pipeline-view');
                    const calendarView = $('#recruitment-calendar-view');

                    if (tableView) tableView.style.display = view === 'table' ? '' : 'none';
                    if (pipelineView) pipelineView.style.display = view === 'pipeline' ? '' : 'none';
                    if (calendarView) calendarView.style.display = view === 'calendar' ? '' : 'none';

                    // Load data for the view
                    if (view === 'pipeline') loadKanbanBoard();
                    if (view === 'calendar') loadInterviewCalendar();
                });
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Escape closes modal
            if (e.key === 'Escape' && !dom.modalOverlay.hidden) {
                closeModal();
                return;
            }
            // Don't trigger shortcuts when typing in inputs
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

            // Ctrl+K / Cmd+K -> Global Search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                openGlobalSearch();
                return;
            }
            // D -> Toggle dark mode
            if (e.key === 'd' || e.key === 'D') { toggleDarkMode(); return; }
            // N -> New item (context-dependent)
            if (e.key === 'n' || e.key === 'N') {
                if (state.currentSection === 'helpdesk') openCreateTicketModal();
                return;
            }
            // ? -> Keyboard shortcuts help
            if (e.key === '?') { openKeyboardShortcutsHelp(); return; }
        });

        // Periodic health check
        setInterval(checkHealth, 60000);
    }

    /* ============================================================
       FEATURE: Dark Mode (Feature 32)
       ============================================================ */
    function toggleDarkMode() {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('nasiko_theme', next);
        const icon = $('#dark-mode-toggle');
        if (icon) icon.textContent = next === 'dark' ? '\u2600\uFE0F' : '\uD83C\uDF19';
        showToast(`${next === 'dark' ? 'Dark' : 'Light'} mode enabled`, 'info');
    }

    function initDarkMode() {
        const saved = localStorage.getItem('nasiko_theme');
        const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = saved || (systemDark ? 'dark' : 'light');
        document.documentElement.setAttribute('data-theme', theme);
        const icon = $('#dark-mode-toggle');
        if (icon) {
            icon.textContent = theme === 'dark' ? '\u2600\uFE0F' : '\uD83C\uDF19';
            icon.addEventListener('click', toggleDarkMode);
        }
    }

    /* ============================================================
       FEATURE: Global Search (Feature 33)
       ============================================================ */
    function openGlobalSearch() {
        const bodyHtml = `
            <div class="global-search-container">
                <input type="text" class="global-search-input" placeholder="Search candidates, tickets, jobs..." autofocus>
                <div class="global-search-results"></div>
            </div>
        `;
        openModal('Global Search', bodyHtml, {
            size: 'lg',
            onOpen: (modalEl) => {
                const input = modalEl.querySelector('.global-search-input');
                const resultsEl = modalEl.querySelector('.global-search-results');
                let debounceTimer;
                input.addEventListener('input', () => {
                    clearTimeout(debounceTimer);
                    debounceTimer = setTimeout(() => {
                        const q = input.value.trim().toLowerCase();
                        if (q.length < 2) { resultsEl.innerHTML = '<div class="empty-state">Type at least 2 characters...</div>'; return; }
                        let results = [];
                        // Search candidates
                        (state.cache.allCandidates || []).forEach(c => {
                            if ((c.full_name || '').toLowerCase().includes(q) || (c.current_title || '').toLowerCase().includes(q)) {
                                results.push({ type: 'Candidate', name: c.full_name, sub: c.current_title || '', id: c.id, section: 'recruitment' });
                            }
                        });
                        // Search tickets
                        (state.cache.tickets || []).forEach(t => {
                            if ((t.subject || '').toLowerCase().includes(q) || (t.category || '').toLowerCase().includes(q)) {
                                results.push({ type: 'Ticket', name: t.subject, sub: `${t.status} - ${t.priority}`, id: t.id, section: 'helpdesk' });
                            }
                        });
                        // Search jobs
                        (state.cache.jobs || []).forEach(j => {
                            if ((j.title || '').toLowerCase().includes(q) || (j.department || '').toLowerCase().includes(q)) {
                                results.push({ type: 'Job', name: j.title, sub: j.department || '', id: j.id, section: 'recruitment' });
                            }
                        });
                        if (results.length === 0) {
                            resultsEl.innerHTML = '<div class="empty-state">No results found</div>';
                        } else {
                            resultsEl.innerHTML = results.slice(0, 20).map(r => `
                                <div class="search-result-item" data-section="${r.section}" data-id="${r.id}" data-type="${r.type}">
                                    <span class="search-result-type">${r.type}</span>
                                    <span class="search-result-name">${escapeHtml(r.name)}</span>
                                    <span class="search-result-sub">${escapeHtml(r.sub)}</span>
                                </div>
                            `).join('');
                            resultsEl.querySelectorAll('.search-result-item').forEach(item => {
                                item.addEventListener('click', () => {
                                    closeModal();
                                    switchSection(item.dataset.section);
                                    if (item.dataset.type === 'Candidate') openCandidateDetail(item.dataset.id);
                                    if (item.dataset.type === 'Ticket') openTicketDetail(item.dataset.id);
                                });
                            });
                        }
                    }, 300);
                });
            }
        });
    }

    /* ============================================================
       FEATURE: CSV Export (Feature 34)
       ============================================================ */
    function exportToCSV(data, filename, columns) {
        if (!data || data.length === 0) { showToast('No data to export', 'warning'); return; }
        const header = columns.map(c => c.label).join(',');
        const rows = data.map(item => columns.map(c => {
            let val = (item[c.key] ?? '').toString().replace(/"/g, '""');
            return `"${val}"`;
        }).join(','));
        const csv = [header, ...rows].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        showToast(`Exported ${data.length} rows to ${filename}`, 'success');
    }

    function exportCurrentTab() {
        const section = state.currentSection;
        const today = new Date().toISOString().slice(0, 10);
        if (section === 'recruitment') {
            exportToCSV(state.cache.allCandidates, `candidates_${today}.csv`, [
                { key: 'full_name', label: 'Name' }, { key: 'email', label: 'Email' },
                { key: 'status', label: 'Status' }, { key: 'screening_score', label: 'Score' },
                { key: 'current_title', label: 'Title' }, { key: 'years_experience', label: 'Experience' },
            ]);
        } else if (section === 'helpdesk') {
            exportToCSV(state.cache.tickets, `tickets_${today}.csv`, [
                { key: 'subject', label: 'Subject' }, { key: 'category', label: 'Category' },
                { key: 'status', label: 'Status' }, { key: 'priority', label: 'Priority' },
                { key: 'requester_name', label: 'Requester' }, { key: 'created_at', label: 'Created' },
            ]);
        } else if (section === 'compliance') {
            exportToCSV(state.cache.auditLogs, `audit_logs_${today}.csv`, [
                { key: 'action', label: 'Action' }, { key: 'user_email', label: 'User' },
                { key: 'risk_level', label: 'Risk' }, { key: 'created_at', label: 'Timestamp' },
            ]);
        } else {
            showToast('Export not available for this tab', 'info');
        }
    }

    /* ============================================================
       FEATURE: Create Ticket from UI (Feature 18)
       ============================================================ */
    function openCreateTicketModal() {
        const bodyHtml = `
            <div class="form-group">
                <label class="form-label" for="new-ticket-subject">Subject</label>
                <input type="text" id="new-ticket-subject" class="form-input" placeholder="Brief description of the issue" required>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label" for="new-ticket-category">Category</label>
                    <select id="new-ticket-category" class="form-select">
                        <option value="policy">Policy</option>
                        <option value="leave">Leave</option>
                        <option value="benefits">Benefits</option>
                        <option value="payroll">Payroll</option>
                        <option value="complaint">Complaint</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label" for="new-ticket-priority">Priority</label>
                    <select id="new-ticket-priority" class="form-select">
                        <option value="low">Low</option>
                        <option value="medium" selected>Medium</option>
                        <option value="high">High</option>
                        <option value="urgent">Urgent</option>
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label" for="new-ticket-desc">Description</label>
                <textarea id="new-ticket-desc" class="form-input" rows="4" placeholder="Provide details about your issue..."></textarea>
            </div>
        `;
        openModal('New Ticket', bodyHtml, {
            size: 'md',
            footer: '<button class="btn btn-primary" id="create-ticket-submit">Create Ticket</button>',
            onOpen: (modalEl) => {
                modalEl.querySelector('#create-ticket-submit').addEventListener('click', async () => {
                    const subject = modalEl.querySelector('#new-ticket-subject').value.trim();
                    if (!subject) { showToast('Subject is required', 'warning'); return; }
                    const btn = modalEl.querySelector('#create-ticket-submit');
                    try {
                        btn.disabled = true;
                        btn.textContent = 'Creating...';
                        await apiFetch('/api/helpdesk/tickets', {
                            method: 'POST',
                            body: JSON.stringify({
                                subject,
                                category: modalEl.querySelector('#new-ticket-category').value,
                                priority: modalEl.querySelector('#new-ticket-priority').value,
                                description: modalEl.querySelector('#new-ticket-desc').value.trim(),
                            }),
                        });
                        showToast('Ticket created successfully', 'success');
                        closeModal();
                        state.loaded.helpdesk = false;
                        loadHelpdeskData();
                    } catch (err) {
                        showToast(`Failed: ${err.message}`, 'error');
                        btn.disabled = false;
                        btn.textContent = 'Create Ticket';
                    }
                });
            }
        });
    }

    /* ============================================================
       FEATURE: Email Composer (Feature 28)
       ============================================================ */
    function openEmailComposer(to, subject, body) {
        const bodyHtml = `
            <div class="form-group">
                <label class="form-label">To</label>
                <input type="email" class="form-input" id="email-to" value="${escapeHtml(to || '')}" placeholder="recipient@company.com">
            </div>
            <div class="form-group">
                <label class="form-label">Subject</label>
                <input type="text" class="form-input" id="email-subject" value="${escapeHtml(subject || '')}" placeholder="Email subject">
            </div>
            <div class="form-group">
                <label class="form-label">Template</label>
                <select class="form-select" id="email-template">
                    <option value="">Custom message</option>
                    <option value="interview">Interview Invitation</option>
                    <option value="offer">Offer Letter</option>
                    <option value="rejection">Rejection (Empathetic)</option>
                    <option value="ticket_update">Ticket Update</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Body</label>
                <textarea class="form-input" id="email-body" rows="8" placeholder="Type your message...">${escapeHtml(body || '')}</textarea>
            </div>
        `;

        const templates = {
            interview: 'Dear [Name],\n\nWe are pleased to invite you for an interview for the [Position] role at our company.\n\nPlease let us know your availability for the coming week.\n\nBest regards,\nHR Team',
            offer: 'Dear [Name],\n\nWe are thrilled to extend an offer for the [Position] role!\n\nPlease find the offer details attached. We look forward to having you on the team.\n\nBest regards,\nHR Team',
            rejection: 'Dear [Name],\n\nThank you for your interest and the time you invested in the interview process for the [Position] role.\n\nAfter careful consideration, we have decided to move forward with another candidate whose experience more closely matches our current needs.\n\nWe were impressed by your qualifications and encourage you to apply for future openings.\n\nWishing you the very best,\nHR Team',
            ticket_update: 'Hello,\n\nThis is an update regarding your helpdesk ticket.\n\n[Details]\n\nPlease don\'t hesitate to reach out if you have further questions.\n\nBest regards,\nHR Support',
        };

        openModal('Send Email', bodyHtml, {
            size: 'lg',
            footer: '<button class="btn btn-secondary" onclick="document.querySelector(\'.modal-close\').click()">Cancel</button><button class="btn btn-primary" id="email-send-btn">Send Email</button>',
            onOpen: (modalEl) => {
                modalEl.querySelector('#email-template').addEventListener('change', (e) => {
                    if (templates[e.target.value]) {
                        modalEl.querySelector('#email-body').value = templates[e.target.value];
                    }
                });
                modalEl.querySelector('#email-send-btn').addEventListener('click', async () => {
                    const toVal = modalEl.querySelector('#email-to').value.trim();
                    const subVal = modalEl.querySelector('#email-subject').value.trim();
                    const bodyVal = modalEl.querySelector('#email-body').value.trim();
                    if (!toVal || !subVal || !bodyVal) { showToast('All fields are required', 'warning'); return; }
                    try {
                        const btn = modalEl.querySelector('#email-send-btn');
                        btn.disabled = true;
                        btn.textContent = 'Sending...';
                        // Use chat agent to send email via tool
                        await apiFetch('/api/chat/', {
                            method: 'POST',
                            body: JSON.stringify({
                                message: `Send an email to ${toVal} with subject "${subVal}" and body: ${bodyVal}`,
                                conversation_id: state.conversationId,
                            }),
                        });
                        showToast(`Email sent to ${toVal}`, 'success');
                        closeModal();
                    } catch (err) {
                        showToast(`Failed: ${err.message}`, 'error');
                    }
                });
            }
        });
    }

    /* ============================================================
       FEATURE: Notification Center (Feature 29)
       ============================================================ */
    function initNotificationCenter() {
        const bell = $('#notification-bell');
        if (!bell) return;
        bell.addEventListener('click', () => {
            const dropdown = $('#notification-dropdown');
            if (dropdown) dropdown.classList.toggle('visible');
        });
        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#notification-bell') && !e.target.closest('#notification-dropdown')) {
                const dropdown = $('#notification-dropdown');
                if (dropdown) dropdown.classList.remove('visible');
            }
        });
    }

    /* ============================================================
       FEATURE: Keyboard Shortcuts Help (Feature 36)
       ============================================================ */
    function openKeyboardShortcutsHelp() {
        const shortcuts = [
            { key: 'Ctrl+K', desc: 'Open global search' },
            { key: 'D', desc: 'Toggle dark mode' },
            { key: 'N', desc: 'New item (ticket, etc.)' },
            { key: 'Esc', desc: 'Close modal' },
            { key: '?', desc: 'Show this help' },
        ];
        const bodyHtml = '<div class="shortcuts-list">' + shortcuts.map(s =>
            `<div class="shortcut-row"><kbd>${s.key}</kbd><span>${s.desc}</span></div>`
        ).join('') + '</div>';
        openModal('Keyboard Shortcuts', bodyHtml, { size: 'sm' });
    }

    /* ============================================================
       FEATURE: Audit Log Detail Modal (Feature 25)
       ============================================================ */
    function openAuditLogDetail(logEntry) {
        if (!logEntry) return;
        const bodyHtml = `
            <div class="candidate-profile">
                <div class="profile-field"><span class="profile-field-label">Action</span><span class="profile-field-value">${escapeHtml(logEntry.action || '')}</span></div>
                <div class="profile-field"><span class="profile-field-label">User</span><span class="profile-field-value">${escapeHtml(logEntry.user_email || logEntry.user_name || '')}</span></div>
                <div class="profile-field"><span class="profile-field-label">Role</span><span class="profile-field-value">${escapeHtml(logEntry.user_role || '')}</span></div>
                <div class="profile-field"><span class="profile-field-label">Timestamp</span><span class="profile-field-value">${absoluteTime(logEntry.created_at)}</span></div>
                <div class="profile-field"><span class="profile-field-label">Risk Level</span><span class="profile-field-value"><span class="badge badge-${logEntry.risk_level || 'low'}">${logEntry.risk_level || 'low'}</span></span></div>
                <div class="profile-field"><span class="profile-field-label">Agent</span><span class="profile-field-value">${escapeHtml(logEntry.agent_name || 'N/A')}</span></div>
            </div>
            ${logEntry.input_text ? `<div class="profile-section"><h4>Input</h4><pre class="audit-detail-pre">${escapeHtml(logEntry.input_text)}</pre></div>` : ''}
            ${logEntry.output_text ? `<div class="profile-section"><h4>Output</h4><pre class="audit-detail-pre">${escapeHtml(logEntry.output_text)}</pre></div>` : ''}
        `;
        openModal('Audit Log Detail', bodyHtml, { size: 'lg' });
    }

    /* ============================================================
       FEATURE: User Settings Panel (Feature 35)
       ============================================================ */
    function openUserSettings() {
        const bodyHtml = `
            <div class="candidate-profile">
                <div class="profile-field"><span class="profile-field-label">Email</span><span class="profile-field-value">${escapeHtml(state.userEmail || '')}</span></div>
                <div class="profile-field"><span class="profile-field-label">Role</span><span class="profile-field-value">${escapeHtml(state.userRole || '')}</span></div>
                <div class="profile-field"><span class="profile-field-label">Tenant</span><span class="profile-field-value">${escapeHtml(state.tenantId || '')}</span></div>
            </div>
            <div class="profile-section">
                <h4>Preferences</h4>
                <div class="form-group">
                    <label class="form-label">Theme</label>
                    <select class="form-select" id="settings-theme">
                        <option value="light" ${document.documentElement.getAttribute('data-theme') !== 'dark' ? 'selected' : ''}>Light</option>
                        <option value="dark" ${document.documentElement.getAttribute('data-theme') === 'dark' ? 'selected' : ''}>Dark</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Default Recruitment View</label>
                    <select class="form-select" id="settings-rec-view">
                        <option value="table" ${state.recruitmentView === 'table' ? 'selected' : ''}>Table</option>
                        <option value="pipeline" ${state.recruitmentView === 'pipeline' ? 'selected' : ''}>Pipeline (Kanban)</option>
                        <option value="calendar" ${state.recruitmentView === 'calendar' ? 'selected' : ''}>Calendar</option>
                    </select>
                </div>
            </div>
        `;
        openModal('User Settings', bodyHtml, {
            size: 'md',
            footer: '<button class="btn btn-primary" id="save-settings-btn">Save</button>',
            onOpen: (modalEl) => {
                modalEl.querySelector('#save-settings-btn').addEventListener('click', () => {
                    const theme = modalEl.querySelector('#settings-theme').value;
                    document.documentElement.setAttribute('data-theme', theme);
                    localStorage.setItem('nasiko_theme', theme);
                    state.recruitmentView = modalEl.querySelector('#settings-rec-view').value;
                    showToast('Settings saved', 'success');
                    closeModal();
                });
            }
        });
    }

    /* ============================================================
       FEATURE: Job Posting Editor (Feature 10)
       ============================================================ */
    function openJobEditor(job) {
        if (!job) return;
        const bodyHtml = `
            <div class="form-group"><label class="form-label">Title</label><input type="text" class="form-input" id="edit-job-title" value="${escapeHtml(job.title || '')}"></div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Department</label><input type="text" class="form-input" id="edit-job-dept" value="${escapeHtml(job.department || '')}"></div>
                <div class="form-group"><label class="form-label">Location</label><input type="text" class="form-input" id="edit-job-location" value="${escapeHtml(job.location || '')}"></div>
            </div>
            <div class="form-group"><label class="form-label">Description</label><textarea class="form-input" id="edit-job-desc" rows="5">${escapeHtml(job.description || '')}</textarea></div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Salary Min</label><input type="number" class="form-input" id="edit-job-salmin" value="${job.salary_min || ''}"></div>
                <div class="form-group"><label class="form-label">Salary Max</label><input type="number" class="form-input" id="edit-job-salmax" value="${job.salary_max || ''}"></div>
            </div>
            <div class="form-group"><label class="form-label">Status</label>
                <select class="form-select" id="edit-job-status">
                    <option value="open" ${job.status === 'open' ? 'selected' : ''}>Open</option>
                    <option value="paused" ${job.status === 'paused' ? 'selected' : ''}>Paused</option>
                    <option value="closed" ${job.status === 'closed' ? 'selected' : ''}>Closed</option>
                </select>
            </div>
        `;
        openModal('Edit Job: ' + (job.title || ''), bodyHtml, {
            size: 'lg',
            footer: '<button class="btn btn-ghost" onclick="document.querySelector(\'.modal-close\').click()">Cancel</button><button class="btn btn-primary" id="save-job-btn">Save Changes</button><button class="btn btn-ghost" style="color:var(--color-error)" id="archive-job-btn">Archive Job</button>',
            onOpen: (modalEl) => {
                modalEl.querySelector('#save-job-btn').addEventListener('click', async () => {
                    try {
                        const btn = modalEl.querySelector('#save-job-btn');
                        btn.disabled = true;
                        btn.textContent = 'Saving...';
                        await apiFetch(`/api/recruitment/jobs/${job.id}`, {
                            method: 'PATCH',
                            body: JSON.stringify({
                                title: modalEl.querySelector('#edit-job-title').value.trim() || undefined,
                                description: modalEl.querySelector('#edit-job-desc').value.trim() || undefined,
                                location: modalEl.querySelector('#edit-job-location').value.trim() || undefined,
                                salary_min: parseFloat(modalEl.querySelector('#edit-job-salmin').value) || undefined,
                                salary_max: parseFloat(modalEl.querySelector('#edit-job-salmax').value) || undefined,
                                status: modalEl.querySelector('#edit-job-status').value,
                            }),
                        });
                        showToast('Job updated successfully', 'success');
                        closeModal();
                        state.loaded.recruitment = false;
                        state.cache.jobs = [];
                        loadRecruitmentData();
                    } catch (err) {
                        showToast(`Failed: ${err.message}`, 'error');
                    }
                });
                modalEl.querySelector('#archive-job-btn').addEventListener('click', async () => {
                    if (!confirm(`Archive "${job.title}"? This will close the job posting.`)) return;
                    try {
                        await apiFetch(`/api/recruitment/jobs/${job.id}`, { method: 'DELETE' });
                        showToast('Job archived', 'success');
                        closeModal();
                        state.loaded.recruitment = false;
                        state.cache.jobs = [];
                        loadRecruitmentData();
                    } catch (err) { showToast(`Failed: ${err.message}`, 'error'); }
                });
            }
        });
    }

    /* ============================================================
       FEATURE: Compliance Report Generator (Feature 27)
       ============================================================ */
    function openComplianceReport() {
        const logs = state.cache.auditLogs || [];
        if (logs.length === 0) { showToast('No audit data available', 'warning'); return; }

        // Aggregate stats
        const actionCounts = {};
        const riskCounts = { low: 0, medium: 0, high: 0 };
        const statusCounts = {};
        logs.forEach(l => {
            actionCounts[l.action || 'unknown'] = (actionCounts[l.action || 'unknown'] || 0) + 1;
            riskCounts[l.risk_level || 'low'] = (riskCounts[l.risk_level || 'low'] || 0) + 1;
            statusCounts[l.status || 'unknown'] = (statusCounts[l.status || 'unknown'] || 0) + 1;
        });

        const topActions = Object.entries(actionCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);

        let bodyHtml = `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
                <div class="metric-card"><div class="metric-info"><span class="metric-value">${logs.length}</span><span class="metric-label">Total Actions</span></div></div>
                <div class="metric-card"><div class="metric-info"><span class="metric-value" style="color:var(--color-error)">${riskCounts.high}</span><span class="metric-label">High Risk</span></div></div>
            </div>
            <div class="profile-section">
                <h4>Risk Distribution</h4>
                <div style="display:flex;gap:4px;height:24px;border-radius:4px;overflow:hidden;margin-top:8px">
                    <div style="flex:${riskCounts.low || 1};background:var(--color-success)" title="Low: ${riskCounts.low}"></div>
                    <div style="flex:${riskCounts.medium || 0.01};background:var(--color-warning)" title="Medium: ${riskCounts.medium}"></div>
                    <div style="flex:${riskCounts.high || 0.01};background:var(--color-error)" title="High: ${riskCounts.high}"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.6875rem;color:var(--color-text-muted);margin-top:4px">
                    <span>Low: ${riskCounts.low}</span><span>Medium: ${riskCounts.medium}</span><span>High: ${riskCounts.high}</span>
                </div>
            </div>
            <div class="profile-section">
                <h4>Top Actions</h4>
                ${topActions.map(([action, count]) => `
                    <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--color-border-light);font-size:0.8125rem">
                        <span>${escapeHtml(action)}</span><strong>${count}</strong>
                    </div>
                `).join('')}
            </div>
        `;

        openModal('Compliance Report', bodyHtml, {
            size: 'lg',
            footer: '<button class="btn btn-primary" id="report-export-btn">Export Report CSV</button>',
            onOpen: (modalEl) => {
                modalEl.querySelector('#report-export-btn').addEventListener('click', () => {
                    exportCurrentTab();
                    closeModal();
                });
            }
        });
    }

    /* ============================================================
       FEATURE: Candidate Comparison (Feature 4)
       ============================================================ */
    function openCandidateComparison(candidateIds) {
        const candidates = candidateIds.map(id => (state.cache.allCandidates || []).find(c => c.id === id)).filter(Boolean);
        if (candidates.length < 2) { showToast('Select at least 2 candidates to compare', 'warning'); return; }

        const metrics = [
            { label: 'Screening Score', key: 'screening_score', max: 100 },
            { label: 'Experience (years)', key: 'years_experience', max: 20 },
        ];

        let bodyHtml = '<div class="comparison-grid" style="display:grid;grid-template-columns:200px ' + candidates.map(() => '1fr').join(' ') + ';gap:1px;">';
        // Header row
        bodyHtml += '<div class="comp-header"></div>';
        candidates.forEach(c => {
            bodyHtml += `<div class="comp-header"><strong>${escapeHtml(c.full_name)}</strong><br><small>${escapeHtml(c.current_title || '')}</small></div>`;
        });
        // Metric rows
        metrics.forEach(m => {
            bodyHtml += `<div class="comp-label">${m.label}</div>`;
            const values = candidates.map(c => c[m.key] || 0);
            const maxVal = Math.max(...values);
            candidates.forEach(c => {
                const val = c[m.key] || 0;
                const isWinner = val === maxVal && maxVal > 0;
                const pct = m.max ? Math.round((val / m.max) * 100) : 0;
                bodyHtml += `<div class="comp-value ${isWinner ? 'comp-winner' : ''}">
                    <span>${val}</span>
                    <div class="comp-bar"><div class="comp-bar-fill" style="width:${pct}%"></div></div>
                </div>`;
            });
        });
        // Skills row
        bodyHtml += '<div class="comp-label">Skills</div>';
        candidates.forEach(c => {
            bodyHtml += `<div class="comp-value">${(c.skills || []).map(s => `<span class="skill-badge">${escapeHtml(s.name)}</span>`).join(' ')}</div>`;
        });
        // Status row
        bodyHtml += '<div class="comp-label">Status</div>';
        candidates.forEach(c => {
            bodyHtml += `<div class="comp-value"><span class="badge badge-${c.status}">${c.status}</span></div>`;
        });
        bodyHtml += '</div>';

        openModal('Candidate Comparison', bodyHtml, { size: 'xl' });
    }

    /* ============================================================
       INIT
       ============================================================ */
    function init() {
        bindEvents();
        if (state.token) {
            showApp();
        } else {
            showLogin();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
