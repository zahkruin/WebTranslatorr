/* ============================================================
   WebTranslatorr Admin - Vanilla JS
   ============================================================ */

// ----------------------------------------------------------
// API Client
// ----------------------------------------------------------
const API = {
    async get(url) {
        const resp = await fetch(url);
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `HTTP ${resp.status}`);
        }
        return resp.json();
    },

    async put(url, data) {
        const resp = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `HTTP ${resp.status}`);
        }
        return resp.json();
    },

    async post(url, data) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `HTTP ${resp.status}`);
        }
        return resp.json();
    },

    async del(url) {
        const resp = await fetch(url, { method: 'DELETE' });
        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            throw new Error(body.detail || `HTTP ${resp.status}`);
        }
        return resp.json();
    }
};

// ----------------------------------------------------------
// Utility helpers
// ----------------------------------------------------------
function $(selector, parent) {
    return (parent || document).querySelector(selector);
}

function $$(selector, parent) {
    return Array.from((parent || document).querySelectorAll(selector));
}

function show(el) {
    el.classList.remove('hidden');
}

function hide(el) {
    el.classList.add('hidden');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ----------------------------------------------------------
// Feedback message helpers
// ----------------------------------------------------------
function showMessage(el, text, type, duration) {
    el.textContent = text;
    el.className = 'message message-' + type;
    show(el);
    if (duration !== 0) {
        setTimeout(function () {
            hide(el);
        }, duration || 3000);
    }
}

function showFeedback(el, text, duration) {
    el.textContent = text;
    el.className = 'feedback-text';
    show(el);
    if (duration !== 0) {
        setTimeout(function () {
            hide(el);
        }, duration || 3000);
    }
}

// ----------------------------------------------------------
// Tab switching
// ----------------------------------------------------------
function initTabs() {
    var tabButtons = $$('.tab-btn');
    var panels = $$('.tab-panel');

    tabButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var tabName = btn.getAttribute('data-tab');

            // Update active tab
            tabButtons.forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');

            // Show matching panel
            panels.forEach(function (p) { p.classList.remove('active'); });
            var panel = document.getElementById('panel-' + tabName);
            if (panel) {
                panel.classList.add('active');
            }
        });
    });
}

// ----------------------------------------------------------
// Provider type classification
// ----------------------------------------------------------
var VIDEO_PROVIDERS = ['mejortorrent', 'dontorrent', 'divxtotal', 'elitetorrent'];

function getProviderType(provider) {
    // Use capabilities if available
    if (provider.capabilities) {
        if (provider.capabilities.supports_movie_search || provider.capabilities.supports_tv_search) {
            return 'video';
        }
        if (provider.capabilities.supports_book_search) {
            return 'books';
        }
    }
    // Fallback to hardcoded list
    if (VIDEO_PROVIDERS.indexOf(provider.provider_id) !== -1) {
        return 'video';
    }
    return 'books';
}

function matchProviderFilter(providerType, filter) {
    if (filter === 'all') return true;
    return providerType === filter;
}

// ----------------------------------------------------------
// Provider Test helpers
// ----------------------------------------------------------

function buildTestCell(provider) {
    var lastStatus = provider.last_test_status || '';
    var latency = provider.last_test_latency_ms;
    var error = provider.last_test_error || '';

    var html = '<div class="test-cell-wrapper">' +
        '<button class="btn btn-sm btn-test-provider"' +
            ' data-provider-id="' + escapeHtml(provider.provider_id) + '"' +
            ' onclick="testProviderFromButton(this)"' +
            ' title="Test connectivity for ' + escapeHtml(provider.provider_id) + '">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>' +
            '</svg>' +
        '</button>' +
        '<span class="test-result-inline" id="test-result-' + escapeHtml(provider.provider_id) + '">';

    if (lastStatus) {
        if (lastStatus === 'ok') {
            html += '<span class="test-badge test-ok" title="' +
                (latency ? latency + 'ms' : '') + ' — HTTP ' + (provider.last_test_http_status || '?') + '">' +
                'OK ' + (latency ? latency + 'ms' : '') + '</span>';
        } else if (lastStatus === 'auth_required') {
            html += '<span class="test-badge test-warn" title="' +
                escapeHtml(error) + '">HTTP ' + (provider.last_test_http_status || '?') + '</span>';
        } else {
            html += '<span class="test-badge test-fail" title="' +
                escapeHtml(error) + '">' + (lastStatus === 'timeout' ? 'Timeout' : 'Error') + '</span>';
        }
    }

    html += '</span></div>';
    return html;
}

async function testProviderFromButton(button) {
    var providerId = button.getAttribute('data-provider-id');
    var resultEl = document.getElementById('test-result-' + providerId);

    var origHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner spinner-sm"></span>';
    if (resultEl) resultEl.innerHTML = '';

    try {
        var data = await API.post('/api/admin/providers/' + encodeURIComponent(providerId) + '/test');
        updateTestIndicator(providerId, data);
    } catch (err) {
        if (resultEl) {
            resultEl.innerHTML = '<span class="test-badge test-fail" title="' +
                escapeHtml(err.message) + '">Error</span>';
        }
    } finally {
        button.disabled = false;
        button.innerHTML = origHtml;
    }
}

function updateTestIndicator(providerId, result) {
    var resultEl = document.getElementById('test-result-' + providerId);
    if (!resultEl) return;

    if (result.status === 'ok') {
        resultEl.innerHTML = '<span class="test-badge test-ok" title="' +
            (result.latency_ms ? result.latency_ms + 'ms' : '') + ' — HTTP ' + (result.http_status || '?') + '">' +
            'OK ' + (result.latency_ms ? result.latency_ms + 'ms' : '') + '</span>';
    } else if (result.status === 'auth_required') {
        resultEl.innerHTML = '<span class="test-badge test-warn" title="' +
            escapeHtml(result.error_message || '') + '">HTTP ' + (result.http_status || '?') + '</span>';
    } else {
        var label = result.status === 'timeout' ? 'Timeout' : 'Error';
        resultEl.innerHTML = '<span class="test-badge test-fail" title="' +
            escapeHtml(result.error_message || '') + '">' + label + '</span>';
    }
}

async function testAllProviders() {
    var btn = document.getElementById('test-all-btn');
    var progress = document.getElementById('test-all-progress');
    if (!btn) return;

    var origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinner-sm"></span> Testing all...';
    hide(progress);

    try {
        var data = await API.post('/api/admin/providers/test-all');
        var results = data.results || [];
        var summary = data.summary || {};

        results.forEach(function (r) {
            updateTestIndicator(r.provider_id, r);
        });

        var total = summary.total || results.length;
        var ok = summary.ok || 0;
        var failed = summary.failed || (total - ok);

        showFeedback(progress,
            ok + ' OK, ' + failed + ' failed out of ' + total,
            6000);
        progress.style.color = failed > 0 ? 'var(--warning)' : 'var(--success)';
        progress.className = 'feedback-text';
    } catch (err) {
        showFeedback(progress, 'Test all failed: ' + escapeHtml(err.message), 5000);
        progress.style.color = 'var(--danger)';
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
    }
}

function initTestAllButton() {
    var btn = document.getElementById('test-all-btn');
    if (btn) {
        btn.addEventListener('click', testAllProviders);
    }
}

// ----------------------------------------------------------
// Providers Panel
// ----------------------------------------------------------
var currentFilter = 'all';
var allProviders = [];

function initProviderFilters() {
    var filterBtns = $$('.filter-btn');
    filterBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            filterBtns.forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter');
            renderProviderTable();
        });
    });
}

function loadProviders() {
    var loader = $('#providers-loader');
    var error = $('#providers-error');
    var empty = $('#providers-empty');
    var tableWrapper = $('#providers-table-wrapper');

    show(loader);
    hide(error);
    hide(empty);
    hide(tableWrapper);

    API.get('/api/admin/providers')
        .then(function (data) {
            allProviders = data.providers || [];
            hide(loader);
            if (allProviders.length === 0) {
                show(empty);
            } else {
                show(tableWrapper);
                renderProviderTable();
            }
        })
        .catch(function (err) {
            hide(loader);
            showMessage(error, 'Error loading providers: ' + escapeHtml(err.message), 'error', 0);
        });
}

function renderProviderTable() {
    var tbody = $('#providers-tbody');
    tbody.innerHTML = '';

    var filtered = allProviders.filter(function (p) {
        return matchProviderFilter(getProviderType(p), currentFilter);
    });

    if (filtered.length === 0) {
        var row = document.createElement('tr');
        var cell = document.createElement('td');
        cell.colSpan = 7;
        cell.style.textAlign = 'center';
        cell.style.color = 'var(--text-secondary)';
        cell.style.padding = '20px';
        cell.textContent = 'No providers match the current filter.';
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }

    filtered.forEach(function (provider) {
        var type = getProviderType(provider);
        var typeBadge = type === 'books'
            ? '<span class="badge badge-books">Books</span>'
            : '<span class="badge badge-video">Video</span>';

        var checked = provider.enabled ? ' checked' : '';
        var enabledHtml =
            '<label class="toggle-switch">' +
                '<input type="checkbox" ' + checked +
                    ' data-provider-id="' + escapeHtml(provider.provider_id) + '"' +
                    ' onchange="toggleProvider(this)">' +
                '<span class="toggle-slider"></span>' +
            '</label>';

        var domainHtml =
            '<div style="display:flex;align-items:center;gap:6px;">' +
                '<input type="text" class="cell-domain-input" value="' + escapeHtml(provider.domain || '') + '"' +
                    ' data-provider-id="' + escapeHtml(provider.provider_id) + '"' +
                    ' placeholder="Custom domain">' +
                '<button class="btn btn-sm btn-primary" onclick="saveProviderDomain(this)"' +
                    ' data-provider-id="' + escapeHtml(provider.provider_id) + '"' +
                    ' title="Save domain for ' + escapeHtml(provider.provider_id) + '">Save</button>' +
            '</div>';

        var testHtml = buildTestCell(provider);

        var row = document.createElement('tr');
        row.setAttribute('data-type', type);
        row.innerHTML =
            '<td class="cell-id">' + escapeHtml(provider.provider_id) + '</td>' +
            '<td class="cell-name">' + escapeHtml(provider.display_name || provider.provider_id) + '</td>' +
            '<td class="cell-type">' + typeBadge + '</td>' +
            '<td class="cell-enabled">' + enabledHtml + '</td>' +
            '<td class="cell-domain">' + domainHtml + '</td>' +
            '<td class="cell-test">' + testHtml + '</td>';
        tbody.appendChild(row);
    });
}

// Toggle provider enabled/disabled
async function toggleProvider(checkbox) {
    var providerId = checkbox.getAttribute('data-provider-id');
    var enabled = checkbox.checked;

    // Optimistic update
    checkbox.disabled = true;

    try {
        await API.put('/api/admin/providers/' + encodeURIComponent(providerId), {
            enabled: enabled
        });
        // Reload registry after toggle
        try {
            await API.post('/api/admin/providers/reload');
        } catch (e) {
            console.warn('Reload after toggle failed:', e);
        }
        // Refresh table to get updated state
        await loadProviders();
    } catch (err) {
        // Revert optimistic update
        checkbox.checked = !enabled;
        checkbox.disabled = false;
        var feedback = $('#reload-feedback');
        showFeedback(feedback, 'Failed to update ' + providerId + ': ' + err.message, 5000);
        feedback.className = 'feedback-text';
        feedback.style.color = 'var(--danger)';
    }
}

// Save provider domain
async function saveProviderDomain(button) {
    var providerId = button.getAttribute('data-provider-id');
    var input = document.querySelector('.cell-domain-input[data-provider-id="' + providerId + '"]');
    if (!input) return;

    var newDomain = input.value.trim();
    button.disabled = true;
    button.textContent = 'Saving...';

    try {
        await API.put('/api/admin/providers/' + encodeURIComponent(providerId), {
            domain: newDomain
        });
        button.textContent = 'Saved!';
        button.style.backgroundColor = 'var(--success)';
        setTimeout(function () {
            button.textContent = 'Save';
            button.disabled = false;
            button.style.backgroundColor = '';
        }, 2000);
    } catch (err) {
        button.textContent = 'Error';
        button.style.backgroundColor = 'var(--danger)';
        setTimeout(function () {
            button.textContent = 'Save';
            button.disabled = false;
            button.style.backgroundColor = '';
        }, 2000);
        var feedback = $('#reload-feedback');
        showFeedback(feedback, 'Failed to save domain: ' + err.message, 5000);
        feedback.style.color = 'var(--danger)';
    }
}

// Reload registry
function initReloadRegistry() {
    var btn = $('#reload-registry-btn');
    if (!btn) return;
    btn.addEventListener('click', async function () {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner spinner-sm"></span> Reloading...';
        var feedback = $('#reload-feedback');
        hide(feedback);

        try {
            var result = await API.post('/api/admin/providers/reload');
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg> Reload Registry';
            var count = result.provider_count || 0;
            showFeedback(feedback, 'Registry reloaded. ' + count + ' providers active.', 3000);
            // Refresh the table
            await loadProviders();
        } catch (err) {
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg> Reload Registry';
            showFeedback(feedback, 'Failed to reload registry: ' + escapeHtml(err.message), 5000);
            feedback.style.color = 'var(--danger)';
        } finally {
            btn.disabled = false;
        }
    });
}

// ----------------------------------------------------------
// Settings Panel
// ----------------------------------------------------------
function loadSettings() {
    var loader = $('#settings-loader');
    var error = $('#settings-error');
    var empty = $('#settings-empty');
    var form = $('#settings-form');

    show(loader);
    hide(error);
    hide(empty);
    hide(form);

    API.get('/api/admin/settings')
        .then(function (data) {
            hide(loader);
            var settings = data.settings || {};
            var keys = Object.keys(settings);

            if (keys.length === 0) {
                show(empty);
            } else {
                show(form);
                keys.forEach(function (key) {
                    var input = document.getElementById('setting-' + key);
                    if (input) {
                        input.value = settings[key] || '';
                    }
                });
            }
        })
        .catch(function (err) {
            hide(loader);
            showMessage(error, 'Error loading settings: ' + escapeHtml(err.message), 'error', 0);
        });
}

function initSettingsSave() {
    var buttons = $$('.btn-save-setting');
    buttons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var key = btn.getAttribute('data-key');
            var input = document.getElementById('setting-' + key);
            if (!input) return;
            var value = input.value;
            var feedback = document.querySelector('.save-feedback[data-key="' + key + '"]');

            btn.disabled = true;
            btn.textContent = 'Saving...';

            API.put('/api/admin/settings/' + encodeURIComponent(key), { value: value })
                .then(function () {
                    btn.textContent = 'Save';
                    btn.disabled = false;
                    if (feedback) {
                        show(feedback);
                        setTimeout(function () { hide(feedback); }, 2000);
                    }
                })
                .catch(function (err) {
                    btn.textContent = 'Error';
                    btn.style.backgroundColor = 'var(--danger)';
                    setTimeout(function () {
                        btn.textContent = 'Save';
                        btn.disabled = false;
                        btn.style.backgroundColor = '';
                    }, 2000);
                    var globalFeedback = $('#settings-global-feedback');
                    showMessage(globalFeedback, 'Failed to save ' + key + ': ' + escapeHtml(err.message), 'error', 5000);
                });
        });
    });
}

function initSettingsVisibilityToggles() {
    var buttons = $$('.toggle-visibility-btn');
    buttons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var targetId = btn.getAttribute('data-target');
            var input = document.getElementById(targetId);
            if (!input) return;

            if (input.type === 'password') {
                input.type = 'text';
                btn.innerHTML = '<svg class="eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
            } else {
                input.type = 'password';
                btn.innerHTML = '<svg class="eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
            }
        });
    });
}

// ----------------------------------------------------------
// Readarr Panel
// ----------------------------------------------------------
var editingInstanceId = null;

function loadInstances() {
    var loader = $('#readarr-loader');
    var error = $('#readarr-error');
    var empty = $('#readarr-empty');
    var grid = $('#readarr-instances');

    show(loader);
    hide(error);
    hide(empty);
    grid.innerHTML = '';

    API.get('/api/admin/readarr')
        .then(function (data) {
            hide(loader);
            var instances = data.instances || [];

            if (instances.length === 0) {
                show(empty);
            } else {
                instances.forEach(function (inst) {
                    grid.appendChild(buildInstanceCard(inst));
                });
            }
        })
        .catch(function (err) {
            hide(loader);
            showMessage(error, 'Error loading instances: ' + escapeHtml(err.message), 'error', 0);
        });
}

function buildInstanceCard(instance) {
    var card = document.createElement('div');
    card.className = 'instance-card';
    card.setAttribute('data-instance-id', instance.id);

    var enabledBadge = instance.enabled !== false
        ? '<span class="badge badge-success">Enabled</span>'
        : '<span class="badge badge-danger">Disabled</span>';

    card.innerHTML =
        '<div class="instance-header">' +
            '<div class="instance-info">' +
                '<span class="instance-name">' + escapeHtml(instance.name) + '</span>' +
                '<span class="instance-url">' + escapeHtml(instance.url) + '</span>' +
                enabledBadge +
            '</div>' +
            '<div class="instance-actions">' +
                '<button class="btn btn-primary btn-sm test-conn-btn" data-id="' + instance.id + '" title="Test connection">' +
                    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> Test' +
                '</button>' +
                '<button class="btn btn-primary btn-sm sync-btn" data-id="' + instance.id + '" title="Sync providers now">' +
                    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg> Sync Now' +
                '</button>' +
                '<button class="btn btn-secondary btn-sm edit-btn" data-id="' + instance.id + '" title="Edit instance">' +
                    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Edit' +
                '</button>' +
                '<button class="btn btn-danger btn-sm delete-btn" data-id="' + instance.id + '" title="Delete instance">' +
                    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg> Delete' +
                '</button>' +
            '</div>' +
        '</div>' +
        '<div class="instance-body" id="body-' + instance.id + '">' +
            '<div class="edit-form-container" id="edit-form-' + instance.id + '" style="display:none;"></div>' +
            '<div class="sync-result-container" id="sync-result-' + instance.id + '"></div>' +
            '<div class="test-result-container" id="test-result-' + instance.id + '"></div>' +
        '</div>';

    // Attach event listeners
    setTimeout(function () {
        var testBtn = card.querySelector('.test-conn-btn');
        var syncBtn = card.querySelector('.sync-btn');
        var editBtn = card.querySelector('.edit-btn');
        var deleteBtn = card.querySelector('.delete-btn');

        if (testBtn) testBtn.addEventListener('click', function () { testConnection(instance.id); });
        if (syncBtn) syncBtn.addEventListener('click', function () { syncInstance(instance.id); });
        if (editBtn) editBtn.addEventListener('click', function () { showEditForm(instance); });
        if (deleteBtn) deleteBtn.addEventListener('click', function () { deleteInstance(instance.id); });
    }, 0);

    return card;
}

// Add instance
function initAddInstanceForm() {
    var form = $('#add-readarr-form');
    if (!form) return;

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        var nameInput = $('#readarr-name');
        var urlInput = $('#readarr-url');
        var apiKeyInput = $('#readarr-api-key');
        var externalUrlInput = $('#readarr-external-url');
        var feedback = $('#add-readarr-feedback');
        var submitBtn = form.querySelector('button[type="submit"]');

        var name = nameInput.value.trim();
        var url = urlInput.value.trim();
        var apiKey = apiKeyInput.value.trim();
        var externalUrl = externalUrlInput ? externalUrlInput.value.trim() : '';

        if (!name || !url || !apiKey) {
            showMessage(feedback, 'All fields are required.', 'warning', 3000);
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Adding...';
        hide(feedback);

        try {
            await API.post('/api/admin/readarr', {
                name: name,
                url: url,
                api_key: apiKey,
                external_url: externalUrl
            });
            nameInput.value = '';
            urlInput.value = '';
            apiKeyInput.value = '';
            if (externalUrlInput) externalUrlInput.value = '';
            showMessage(feedback, 'Instance added successfully!', 'success', 3000);
            loadInstances();
        } catch (err) {
            showMessage(feedback, 'Failed to add instance: ' + escapeHtml(err.message), 'error', 5000);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Add Instance';
        }
    });
}

// Delete instance
async function deleteInstance(id) {
    if (!confirm('Are you sure you want to delete this Readarr instance? This cannot be undone.')) return;

    try {
        await API.del('/api/admin/readarr/' + id);
        loadInstances();
    } catch (err) {
        var card = document.querySelector('.instance-card[data-instance-id="' + id + '"]');
        if (card) {
            var errorEl = document.createElement('div');
            errorEl.className = 'message message-error';
            errorEl.textContent = 'Error deleting: ' + err.message;
            errorEl.style.marginTop = '8px';
            var body = card.querySelector('.instance-body');
            if (body) {
                body.prepend(errorEl);
                setTimeout(function () { errorEl.remove(); }, 5000);
            }
        }
    }
}

// Test connection
async function testConnection(id) {
    var resultContainer = $('#test-result-' + id);
    var btn = document.querySelector('.test-conn-btn[data-id="' + id + '"]');

    if (btn) {
        btn.disabled = true;
        var origHtml = btn.innerHTML;
        btn.innerHTML = '<span class="spinner spinner-sm"></span> Testing...';
    }

    resultContainer.innerHTML = '';

    try {
        var result = await API.post('/api/admin/readarr/' + id + '/test');
        var version = result.version || 'unknown';
        var statusHtml = '<div class="message message-success">' +
            '<strong>Connection successful!</strong> Readarr version: ' + escapeHtml(version) + '</div>';
        resultContainer.innerHTML = statusHtml;
        setTimeout(function () { resultContainer.innerHTML = ''; }, 8000);
    } catch (err) {
        resultContainer.innerHTML = '<div class="message message-error">' +
            '<strong>Connection failed:</strong> ' + escapeHtml(err.message) + '</div>';
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> Test';
        }
    }
}

// Sync instance
async function syncInstance(id) {
    var resultContainer = $('#sync-result-' + id);
    var btn = document.querySelector('.sync-btn[data-id="' + id + '"]');

    if (btn) {
        btn.disabled = true;
        var origHtml = btn.innerHTML;
        btn.innerHTML = '<span class="spinner spinner-sm"></span> Syncing...';
    }

    resultContainer.innerHTML = '<div style="color:var(--text-secondary);padding:8px 0;">Syncing...</div>';

    try {
        var result = await API.post('/api/admin/readarr/' + id + '/sync');
        resultContainer.innerHTML = buildSyncResultsHtml(result);
    } catch (err) {
        resultContainer.innerHTML = '<div class="message message-error">' +
            '<strong>Sync failed:</strong> ' + escapeHtml(err.message) + '</div>';
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg> Sync Now';
        }
    }
}

function buildSyncResultsHtml(result) {
    var created = result.created || [];
    var updated = result.updated || [];
    var deleted = result.deleted || [];
    var failed = result.failed || [];
    var status = result.status || '';

    var html = '';

    if (status) {
        html += '<div class="message message-info"><strong>Status:</strong> ' + escapeHtml(status) + '</div>';
    }

    html += '<div style="display:flex;gap:16px;margin-bottom:12px;flex-wrap:wrap;">';
    html += '<span class="badge badge-success">Created: ' + created.length + '</span>';
    html += '<span class="badge badge-books">Updated: ' + updated.length + '</span>';
    if (deleted.length > 0) {
        html += '<span class="badge badge-danger">Deleted: ' + deleted.length + '</span>';
    }
    if (failed.length > 0) {
        html += '<span class="badge badge-danger">Failed: ' + failed.length + '</span>';
    }
    html += '</div>';

    if (created.length > 0) {
        html += '<details style="margin-bottom:8px;"><summary style="color:var(--success);cursor:pointer;">Created (' + created.length + ')</summary>';
        html += '<table class="sync-results"><thead><tr><th>Indexer</th><th>ID</th></tr></thead><tbody>';
        created.forEach(function (item) {
            html += '<tr><td>' + escapeHtml(item.name || item) + '</td><td style="font-family:monospace;font-size:0.8rem;color:var(--text-secondary);">' + escapeHtml(String(item.id || item)) + '</td></tr>';
        });
        html += '</tbody></table></details>';
    }

    if (updated.length > 0) {
        html += '<details style="margin-bottom:8px;"><summary style="color:var(--accent);cursor:pointer;">Updated (' + updated.length + ')</summary>';
        html += '<table class="sync-results"><thead><tr><th>Indexer</th><th>ID</th></tr></thead><tbody>';
        updated.forEach(function (item) {
            html += '<tr><td>' + escapeHtml(item.name || item) + '</td><td style="font-family:monospace;font-size:0.8rem;color:var(--text-secondary);">' + escapeHtml(String(item.id || item)) + '</td></tr>';
        });
        html += '</tbody></table></details>';
    }

    if (failed.length > 0) {
        html += '<details style="margin-bottom:8px;"><summary style="color:var(--danger);cursor:pointer;">Failed (' + failed.length + ')</summary>';
        html += '<table class="sync-results"><thead><tr><th>Indexer</th><th>Error</th></tr></thead><tbody>';
        failed.forEach(function (item) {
            html += '<tr><td>' + escapeHtml(item.name || item) + '</td><td style="color:var(--danger);">' + escapeHtml(item.error || String(item)) + '</td></tr>';
        });
        html += '</tbody></table></details>';
    }

    if (created.length === 0 && updated.length === 0 && failed.length === 0 && deleted.length === 0) {
        html += '<div class="message message-info">Sync completed with no changes.</div>';
    }

    return html;
}

// Edit instance (inline)
function showEditForm(instance) {
    var formContainer = $('#edit-form-' + instance.id);
    if (!formContainer) return;

    formContainer.innerHTML =
        '<div class="edit-readarr-form">' +
            '<div class="form-group">' +
                '<label class="form-label">Name</label>' +
                '<input type="text" id="edit-name-' + instance.id + '" class="form-input" value="' + escapeHtml(instance.name) + '">' +
            '</div>' +
            '<div class="form-group">' +
                '<label class="form-label">Readarr URL</label>' +
                '<input type="url" id="edit-url-' + instance.id + '" class="form-input" value="' + escapeHtml(instance.url) + '">' +
            '</div>' +
            '<div class="form-group">' +
                '<label class="form-label">API Key</label>' +
                '<input type="password" id="edit-api-key-' + instance.id + '" class="form-input" placeholder="Leave empty to keep current">' +
            '</div>' +
            '<div class="form-group">' +
                '<label class="form-label">WebTranslatorr URL <span style="font-weight:normal;color:var(--muted);">(how Readarr reaches WTR)</span></label>' +
                '<input type="url" id="edit-external-url-' + instance.id + '" class="form-input" value="' + escapeHtml(instance.external_url || '') + '" placeholder="Uses global EXTERNAL_URL if empty">' +
            '</div>' +
            '<div class="form-group">' +
                '<button class="btn btn-primary btn-sm" onclick="saveEditForm(' + instance.id + ')">Save Changes</button>' +
                '<button class="btn btn-secondary btn-sm" onclick="cancelEdit(' + instance.id + ')" style="margin-left:4px;">Cancel</button>' +
            '</div>' +
        '</div>';

    formContainer.style.display = 'block';
}

async function saveEditForm(id) {
    var nameInput = $('#edit-name-' + id);
    var urlInput = $('#edit-url-' + id);
    var apiKeyInput = $('#edit-api-key-' + id);
    var externalUrlInput = $('#edit-external-url-' + id);
    var formContainer = $('#edit-form-' + id);

    var data = {};
    if (nameInput && nameInput.value.trim()) data.name = nameInput.value.trim();
    if (urlInput && urlInput.value.trim()) data.url = urlInput.value.trim();
    if (apiKeyInput && apiKeyInput.value.trim()) data.api_key = apiKeyInput.value.trim();
    if (externalUrlInput) data.external_url = externalUrlInput.value.trim();

    if (Object.keys(data).length === 0) {
        formContainer.innerHTML = '<div class="message message-warning">No changes to save.</div>';
        setTimeout(function () { formContainer.style.display = 'none'; }, 2000);
        return;
    }

    try {
        await API.put('/api/admin/readarr/' + id, data);
        formContainer.style.display = 'none';
        loadInstances();
    } catch (err) {
        formContainer.innerHTML = '<div class="message message-error">Error saving: ' + escapeHtml(err.message) + '</div>' + formContainer.innerHTML;
    }
}

function cancelEdit(id) {
    var formContainer = $('#edit-form-' + id);
    if (formContainer) {
        formContainer.style.display = 'none';
        formContainer.innerHTML = '';
    }
}

// ----------------------------------------------------------
// Initialization
// ----------------------------------------------------------
document.addEventListener('DOMContentLoaded', function () {
    initTabs();
    initProviderFilters();
    initReloadRegistry();
    initSettingsSave();
    initSettingsVisibilityToggles();
    initAddInstanceForm();
    initTestAllButton();

    // Default tab: Providers
    loadProviders();

    // Preload instances in background
    loadInstances();
});
