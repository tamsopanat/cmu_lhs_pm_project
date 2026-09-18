// --- 1. Chart Data & Configuration ---
        // Initialize with empty defaults, will be populated by FastAPI
        let labelsWeekly = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        let pmWeekly = [0, 0, 0, 0, 0, 0, 0];
        let tempWeekly = [0, 0, 0, 0, 0, 0, 0];

        // Highlighting Logic Functions
        const getPMRadius = (val) => val >= 150 ? 8 : 3;
        const getPMColor = (val) => val >= 150 ? '#ef4444' : '#3b82f6';
        
        const getTempRadius = (val) => val >= 38 ? 8 : 3;
        const getTempColor = (val) => val >= 38 ? '#f97316' : '#94a3b8';

        let envChart = null;
        const envCanvas = document.getElementById('envChart');
        if (envCanvas) {
            const ctx = envCanvas.getContext('2d');
            envChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labelsWeekly,
                datasets: [
                    {
                        label: 'PM2.5 (µg/m³)',
                        data: pmWeekly,
                        borderColor: '#3b82f6',
                        backgroundColor: '#3b82f6',
                        borderWidth: 2,
                        yAxisID: 'y',
                        fill: false, // Clean line without shading
                        tension: 0.4,
                        // Dynamic styling for extreme PM points
                        pointRadius: pmWeekly.map(getPMRadius),
                        pointHoverRadius: pmWeekly.map(val => getPMRadius(val) + 2),
                        pointBackgroundColor: pmWeekly.map(getPMColor),
                        pointBorderColor: pmWeekly.map(val => val >= 150 ? '#ef4444' : '#ffffff'),
                        pointBorderWidth: pmWeekly.map(val => val >= 150 ? 2 : 1),
                    },
                    {
                        label: 'Avg Temperature (°C)',
                        data: tempWeekly,
                        borderColor: '#94a3b8',
                        backgroundColor: '#94a3b8',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        yAxisID: 'y1',
                        fill: false,
                        tension: 0.4,
                        // Dynamic styling for extreme Heat points
                        pointRadius: tempWeekly.map(getTempRadius),
                        pointHoverRadius: tempWeekly.map(val => getTempRadius(val) + 2),
                        pointBackgroundColor: tempWeekly.map(getTempColor),
                        pointBorderColor: tempWeekly.map(val => val >= 38 ? '#f97316' : '#ffffff'),
                        pointBorderWidth: tempWeekly.map(val => val >= 38 ? 2 : 1),
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        backgroundColor: 'rgba(17, 24, 39, 0.9)',
                        titleFont: { size: 13 },
                        bodyFont: { size: 13 },
                        padding: 10,
                        cornerRadius: 8,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y;
                                    // Add warning text in tooltip if critical
                                    if (context.datasetIndex === 0 && context.parsed.y >= 150) {
                                        label += ' ⚠️ CRITICAL';
                                    }
                                    if (context.datasetIndex === 1 && context.parsed.y >= 38) {
                                        label += ' ⚠️ EXTREME HEAT';
                                    }
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'PM2.5 (µg/m³)' },
                        suggestedMax: 200
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Temperature (°C)' },
                        suggestedMin: 20,
                        suggestedMax: 45,
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });

        }

        // --- 2. Toggle Logic ---
        const btnDaily = document.getElementById('btn-daily');
        const btnWeekly = document.getElementById('btn-weekly');

        let locationHierarchy = {};
        
        function toggleFilters() {
            const container = document.getElementById('filter-container');
            const icon = document.getElementById('filter-icon');
            if (!container || !icon) return;
            if (container.classList.contains('hidden')) {
                container.classList.remove('hidden');
                icon.style.transform = "rotate(180deg)";
            } else {
                container.classList.add('hidden');
                icon.style.transform = "rotate(0deg)";
            }
        }

        function getMockHierarchy() {
            return {
                "Chiang Mai": {
                    "Mueang Chiang Mai": ["Suthep", "Chang Phueak", "Sri Phum", "Pa Daet", "Mae Hia"],
                    "Mae Rim": ["Mae Sa", "Rim Tai", "Pong Yaeng"],
                    "Hang Dong": ["Hang Dong", "San Phak Wan", "Nam Phrae"],
                    "San Sai": ["San Sai Luang", "San Pa Pao", "Nong Han"]
                },
                "Lampang": {
                    "Mueang Lampang": ["Phra Bat", "Hua Wiang", "Phichai", "Chomphu", "Pong Saen Thong"],
                    "Ko Kha": ["Ko Kha", "Sala", "Na Kaeo"],
                    "Hang Chat": ["Hang Chat", "Pong Yang Khok"]
                }
            };
        }

        async function fetchLocationHierarchy() {
            if (window.location.protocol === 'blob:' || window.location.protocol === 'data:' || window.location.protocol === 'file:') {
                console.info("Preview mode: Using fallback mock location hierarchy.");
                return getMockHierarchy();
            }
            try {
                const response = await fetch('/api/locations');
                if (!response.ok) throw new Error("Failed to fetch locations");
                return await response.json();
            } catch (error) {
                console.warn("Failed to load locations from API, using fallback", error);
                return getMockHierarchy();
            }
        }

        async function initLocationDropdowns() {
            locationHierarchy = await fetchLocationHierarchy();
            const provSelect = document.getElementById('province-select');
            if (!provSelect) return;
            
            // Populate Provinces
            provSelect.innerHTML = '';
            for (const prov in locationHierarchy) {
                provSelect.innerHTML += `<option value="${prov}">${prov}</option>`;
            }
            
            updateLocationDropdowns('province');
        }

        function updateLocationDropdowns(trigger) {
            const provSelect = document.getElementById('province-select');
            const amphoeSelect = document.getElementById('amphoe-select');
            const tambonSelect = document.getElementById('location-select');
            if (!provSelect || !amphoeSelect || !tambonSelect) return;
            
            const selectedProv = provSelect.value;
            const amphoes = locationHierarchy[selectedProv];

            if (trigger === 'province') {
                // Province changed, update Amphoes
                amphoeSelect.innerHTML = '<option value="All Amphoe">All Amphoe</option>';
                for (const amphoe in amphoes) {
                    amphoeSelect.innerHTML += `<option value="${amphoe}">${amphoe.replace('Mueang ', 'Mueang ')}</option>`;
                }
            }

            const selectedAmphoe = amphoeSelect.value;
            
            if (trigger === 'province' || trigger === 'amphoe') {
                // Province or Amphoe changed, update Tambons
                tambonSelect.innerHTML = '<option value="All Tambon">All Tambon</option>';
                
                if (selectedAmphoe !== 'All Amphoe') {
                    const tambons = amphoes[selectedAmphoe];
                    for (const tambon of tambons) {
                        tambonSelect.innerHTML += `<option value="${tambon}">${tambon}</option>`;
                    }
                }
                
                // Fetch data for the new default tambon/amphoe
                fetchDashboardData();
            }
        }

        // --- Vulnerability Filter Summary & Presets ---
        const FILTER_DEFS = [
            { id: 'chk-child-5', label: 'Children <= 5 yrs' },
            { id: 'chk-newborn', label: 'Newborn (<= 1 yr)' },
            { id: 'chk-athlete', label: 'Outdoor Athlete' },
            { id: 'chk-obesity', label: 'Obesity' },
            { id: 'chk-underweight', label: 'Underweight' },
            { id: 'chk-beta-blocker', label: 'Beta Blocker' },
            { id: 'chk-antihistamine', label: 'Antihistamine' },
            { id: 'chk-diuretic', label: 'Diuretic' },
            { id: 'chk-bpd', label: 'BPD (Active/History)' },
            { id: 'chk-rti', label: 'Recurrent RTI (>=3/6mo)' },
            { id: 'chk-asthma', label: 'Asthma' },
            { id: 'chk-ar', label: 'Allergic Rhinitis' },
            { id: 'chk-chd', label: 'Congenital Heart Dis.' },
            { id: 'chk-fever', label: 'Fever' },
            { id: 'chk-kidney', label: 'Kidney Disease' },
            { id: 'chk-neuro', label: 'Neurologic Disease' },
        ];
        const PRESET_STORAGE_KEY = 'lhs_filter_presets';

        function renderActiveFilters() {
            const summaryEl = document.getElementById('active-filters-summary');
            if (!summaryEl) return;
            const present = FILTER_DEFS.filter(f => document.getElementById(f.id));
            const active = present.filter(f => document.getElementById(f.id).checked);
            if (active.length === 0) {
                summaryEl.innerHTML = '<li class="list-none italic text-gray-500">No parameters selected</li>';
            } else {
                summaryEl.innerHTML = active.map(f => `<li>${f.label}</li>`).join('');
            }
        }

        function applyFilters() {
            fetchDashboardData();
        }

        function clearFilters() {
            FILTER_DEFS.forEach(f => {
                const el = document.getElementById(f.id);
                if (el) el.checked = true;
            });
            fetchDashboardData();
        }

        function getFilterPresets() {
            try {
                return JSON.parse(localStorage.getItem(PRESET_STORAGE_KEY)) || {};
            } catch (e) {
                return {};
            }
        }

        function refreshPresetDropdown() {
            const select = document.getElementById('preset-select');
            if (!select) return;
            const presets = getFilterPresets();
            select.innerHTML = '<option value="">ชุดตัวกรอง</option>';
            Object.keys(presets).forEach(name => {
                select.innerHTML += `<option value="${name}">${name}</option>`;
            });
        }

        function saveFilterPreset() {
            const input = document.getElementById('preset-name-input');
            const name = input?.value.trim();
            if (!name) return;
            const presets = getFilterPresets();
            presets[name] = {};
            FILTER_DEFS.forEach(f => {
                const el = document.getElementById(f.id);
                if (el) presets[name][f.id] = el.checked;
            });
            try {
                localStorage.setItem(PRESET_STORAGE_KEY, JSON.stringify(presets));
            } catch (e) {
                console.warn('Failed to save filter preset', e);
                return;
            }
            input.value = '';
            refreshPresetDropdown();
            document.getElementById('preset-select').value = name;
        }

        function loadFilterPreset(name) {
            if (!name) return;
            const preset = getFilterPresets()[name];
            if (!preset) return;
            FILTER_DEFS.forEach(f => {
                const el = document.getElementById(f.id);
                if (el && f.id in preset) el.checked = preset[f.id];
            });
            fetchDashboardData();
        }

        // --- Role Switching Logic ---
        function switchRole(role) {
            const providerView = document.getElementById('provider-view');
            const adminView = document.getElementById('admin-view');
            const studentParentView = document.getElementById('student-parent-view');
            const roleBadge = document.getElementById('roleBadge');
            
            // Define badge styling
            const badges = {
                'provider': { text: 'Provider View', class: 'text-blue-800 bg-blue-100 border-blue-200' },
                'admin': { text: 'Admin View', class: 'text-purple-800 bg-purple-100 border-purple-200' },
                'student_parent': { text: 'Student & Parent View', class: 'text-green-800 bg-green-100 border-green-200' }
            };

            // Update badge UI
            if (roleBadge) {
                roleBadge.innerText = badges[role].text;
                roleBadge.className = `text-sm font-medium px-3 py-1 rounded-full border shadow-sm transition-colors ${badges[role].class}`;
            }

            [providerView, adminView, studentParentView].forEach(view => view?.classList.add('hidden'));

            const selectedView = {
                provider: providerView,
                admin: adminView,
                student_parent: studentParentView
            }[role];
            selectedView?.classList.remove('hidden');
        }

        // --- 3. API Integration Logic (FastAPI) ---
        let currentMode = 'daily'; // Track state

        btnDaily?.addEventListener('click', () => {
            currentMode = 'daily';
            
            // Update button styles to show Daily is active
            btnDaily.classList.add('text-blue-700', 'bg-blue-50');
            btnDaily.classList.remove('text-gray-900', 'bg-white');
            btnWeekly.classList.add('text-gray-900', 'bg-white');
            btnWeekly.classList.remove('text-blue-700', 'bg-blue-50');
            
            fetchDashboardData(); 
        });

        btnWeekly?.addEventListener('click', () => {
            currentMode = 'weekly';
            
            // Update button styles to show Weekly is active
            btnWeekly.classList.add('text-blue-700', 'bg-blue-50');
            btnWeekly.classList.remove('text-gray-900', 'bg-white');
            btnDaily.classList.add('text-gray-900', 'bg-white');
            btnDaily.classList.remove('text-blue-700', 'bg-blue-50');
            
            fetchDashboardData(); 
        });

        // --- UI Rendering Function ---
        function setText(id, value) {
            const element = document.getElementById(id);
            if (element) element.innerText = value;
        }

        function updateDashboardUI(data) {
            if (envChart) {
            // 1. Update Chart Data
            envChart.data.labels = data.environment.labels;
            envChart.data.datasets[0].data = data.environment.pm25;
            envChart.data.datasets[1].data = data.environment.temperature;
            
            // 2. Update dynamic styling for extreme points
            envChart.data.datasets[0].pointRadius = data.environment.pm25.map(getPMRadius);
            envChart.data.datasets[0].pointHoverRadius = data.environment.pm25.map(val => getPMRadius(val) + 2);
            envChart.data.datasets[0].pointBackgroundColor = data.environment.pm25.map(getPMColor);
            envChart.data.datasets[0].pointBorderColor = data.environment.pm25.map(val => val >= 150 ? '#ef4444' : '#ffffff');
            envChart.data.datasets[0].pointBorderWidth = data.environment.pm25.map(val => val >= 150 ? 2 : 1);
            
            envChart.data.datasets[1].pointRadius = data.environment.temperature.map(getTempRadius);
            envChart.data.datasets[1].pointHoverRadius = data.environment.temperature.map(val => getTempRadius(val) + 2);
            envChart.data.datasets[1].pointBackgroundColor = data.environment.temperature.map(getTempColor);
            envChart.data.datasets[1].pointBorderColor = data.environment.temperature.map(val => val >= 38 ? '#f97316' : '#ffffff');
            envChart.data.datasets[1].pointBorderWidth = data.environment.temperature.map(val => val >= 38 ? 2 : 1);
            
            envChart.update();
            }

            // Update Active Filter Summary & Filtered Result Count
            renderActiveFilters();
            setText('filtered-result-count', data.cohorts.total_risk_count);

            // 3. Update Local Station Grid
            const grid = document.getElementById('local-stations-grid');
            if (grid) {
            grid.innerHTML = ''; // clear grid
            
            if (data.environment.stations && data.environment.stations.length > 0) {
                data.environment.stations.forEach(station => {
                    const isAirHazard = station.pm25 >= 150;
                    const isTempHazard = station.temp >= 38;
                    const isSafe = !isAirHazard && !isTempHazard;

                    let borderClass = 'border-gray-200';
                    let statusBadge = '';

                    if (isAirHazard && isTempHazard) {
                        borderClass = 'border-purple-300 ring-1 ring-purple-100 bg-purple-50/30';
                        statusBadge = `<span class="absolute -top-2.5 -right-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-purple-100 text-purple-700 text-[10px] font-black border border-purple-200 shadow-sm" title="Critical Combined Risk">!</span>`;
                    } else if (isAirHazard) {
                        borderClass = 'border-red-300 ring-1 ring-red-50 bg-red-50/30';
                        statusBadge = `<span class="absolute -top-2.5 -right-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-red-600 text-[10px] font-black border border-red-200 shadow-sm" title="Air Hazard">!</span>`;
                    } else if (isTempHazard) {
                        borderClass = 'border-orange-300 ring-1 ring-orange-50 bg-orange-50/30';
                        statusBadge = `<span class="absolute -top-2.5 -right-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-orange-100 text-orange-600 text-[10px] font-black border border-orange-200 shadow-sm" title="Thermal Hazard">!</span>`;
                    } else {
                        borderClass = 'border-gray-200 hover:border-gray-300';
                    }

                    grid.innerHTML += `
                        <div class="relative rounded-xl border ${borderClass} p-4 shadow-sm transition-all duration-200 hover:shadow-md bg-white">
                            ${statusBadge}
                            <div class="font-bold text-gray-900 text-sm mb-3 truncate" title="${station.name}">${station.name}</div>
                            
                            <div class="space-y-2">
                                <div class="flex items-center justify-between">
                                    <div class="flex items-center gap-1.5 text-xs text-gray-500 font-medium">
                                        <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5"></path></svg>
                                        PM2.5
                                    </div>
                                    <span class="font-bold text-sm ${isAirHazard ? 'text-red-600' : 'text-gray-900'}">${station.pm25}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <div class="flex items-center gap-1.5 text-xs text-gray-500 font-medium">
                                        <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                                        Temp
                                    </div>
                                    <span class="font-bold text-sm ${isTempHazard ? 'text-orange-600' : 'text-gray-900'}">${station.temp}°</span>
                                </div>
                            </div>
                        </div>
                    `;
                });
            } else {
                grid.innerHTML = '<div class="col-span-full text-sm text-gray-500 italic py-2 text-center bg-gray-50 rounded-lg border border-gray-100 border-dashed">No specific local station data available for this view.</div>';
            }
            }

            // 4. Update Cohort Counters
            setText('total-risk-count', `${data.cohorts.total_risk_count} Patients at Risk`);
            setText('air-cohort-count', data.cohorts.air_risk_count);
            setText('thermal-cohort-count', data.cohorts.thermal_risk_count);
            setText('combined-cohort-count', data.cohorts.combined_risk_count);

            // Update Admin View Counters (using unfiltered admin cohorts)
            setText('admin-air-count', `${data.admin_cohorts.air_risk_count} Individuals`);
            setText('admin-thermal-count', `${data.admin_cohorts.thermal_risk_count} Individuals`);
            setText('admin-combined-count', `${data.admin_cohorts.combined_risk_count} Individuals`);

            // 4. Update Patient Table
            const tbody = document.getElementById('patient-table-body');
            if (!tbody) return;
            tbody.innerHTML = ''; // clear table
            
            if (data.patients.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-4 text-center text-gray-500">No high-risk patients meet criteria for this area/period.</td></tr>';
                return;
            }

            data.patients.forEach(p => {
                let riskBadge = '';
                if (p.risk_type === 'COMBINED') riskBadge = `<span class="bg-purple-100 text-purple-800 px-2 py-1 rounded text-xs font-bold border border-purple-200 shadow-sm">CRITICAL</span>`;
                else if (p.risk_type === 'AIR') riskBadge = `<span class="bg-red-100 text-red-800 px-2 py-1 rounded text-xs font-bold border border-red-200 shadow-sm">AIR (PM2.5)</span>`;
                else if (p.risk_type === 'THERMAL') riskBadge = `<span class="bg-orange-100 text-orange-800 px-2 py-1 rounded text-xs font-bold border border-orange-200 shadow-sm">THERMAL</span>`;

                tbody.innerHTML += `
                    <tr class="hover:bg-gray-50 transition border-b border-gray-100">
                        <td class="px-6 py-4">
                            <div class="font-bold text-gray-900">${p.name_masked}</div>
                            <div class="text-xs text-gray-500">ID: ${p.patient_id}</div>
                        </td>
                        <td class="px-6 py-4 text-gray-600">${p.tambon}</td>
                        <td class="px-6 py-4">
                            <div class="flex flex-col gap-1 items-start">
                                ${riskBadge}
                                <span class="text-xs text-gray-500">${p.env_details}</span>
                            </div>
                        </td>
                        <td class="px-6 py-4 text-gray-600 text-xs">${p.flags}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <div class="flex justify-end space-x-2">
                                <button class="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-semibold px-3 py-2 rounded shadow-sm transition">
                                    Log Contact
                                </button>
                                <button onclick="openModal('${p.name_masked}', '${p.flags}', '${p.env_details}')" class="bg-blue-600 hover:text-white hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded shadow-sm transition">
                                    ✨ AI SMS
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            });
        }

        // --- Mock Data Generator (Used in Preview or if API fails) ---
        function loadMockFallback(prov, amphoe, tambon, mode = 'daily') {
            const startDate = new Date(document.getElementById('start-date')?.value || '2026-04-10');
            const endDate = new Date(document.getElementById('end-date')?.value || '2026-05-10');
            const diffDays = Math.floor((endDate - startDate) / (1000 * 60 * 60 * 24));
            
            let labels = [];
            let pm25 = [];
            let temperature = [];
            
            // Build synthetic data arrays based on time window
            if (mode === 'weekly' && diffDays >= 7) {
                let current = new Date(startDate);
                while (current <= endDate) {
                    labels.push(current.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
                    pm25.push(Math.floor(Math.random() * 80) + 60); // 60-140 range
                    temperature.push(Math.round((Math.random() * 8 + 30) * 10) / 10); 
                    current.setDate(current.getDate() + 7);
                }
            } else if (diffDays === 0) {
                // Hourly view
                for (let i = 0; i < 24; i++) {
                    labels.push(`${i.toString().padStart(2, '0')}:00`);
                    pm25.push(Math.floor(Math.random() * 60) + 40);
                    let temp = 28 + (10 * Math.sin((i - 6) * Math.PI / 12)); // Temp curve peaking in afternoon
                    temperature.push(Math.round(temp * 10) / 10);
                }
            } else {
                // Daily view
                let current = new Date(startDate);
                while (current <= endDate) {
                    labels.push(current.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
                    pm25.push(Math.floor(Math.random() * 120) + 50); 
                    temperature.push(Math.round((Math.random() * 12 + 28) * 10) / 10); 
                    current.setDate(current.getDate() + 1);
                }
            }

            // Calculate mock cohorts based on generated chart data
            const max_pm = Math.max(...pm25);
            const max_temp = Math.max(...temperature);

            // Generate mock station data based on the calculated extremes
            let mockStations = [];
            const stationNames = ["รพ.ฝาง", "สถานีอนามัยเวียง", "เทศบาลตำบลเวียง", "รร.ฝางชนูปถัมภ์"];
            stationNames.forEach((name, i) => {
                let stationPM = Math.max(15, Math.floor(max_pm + (Math.random() * 40 - 20)));
                let stationTemp = Math.max(25, Math.round((max_temp + (Math.random() * 2 - 1)) * 10) / 10);
                
                mockStations.push({
                    name: name,
                    pm25: stationPM,
                    temp: stationTemp
                });
            });

            // Mock Checkboxes for Preview Mode
            const chk_child_5 = document.getElementById('chk-child-5')?.checked ?? true;
            const chk_newborn = document.getElementById('chk-newborn')?.checked ?? true;
            const chk_asthma = document.getElementById('chk-asthma')?.checked ?? true;
            
            let mockPatients = [];
            let air_active = max_pm >= 150;
            let temp_active = max_temp >= 38;

            // Patient A: True vulnerabilities: Child <= 5, BPD
            let patA_matches_filter = chk_child_5;
            let patA_true_air = air_active;
            let patA_true_therm = false;
            
            if (patA_matches_filter && patA_true_air) {
                mockPatients.push({
                    name_masked: "Mock Patient A.", patient_id: "CM-MOCK1", tambon: tambon === "All Tambon" ? "Multiple" : tambon,
                    risk_type: "AIR",
                    env_details: `PM2.5: ${Math.floor(max_pm)}`,
                    flags: "Children <= 5 yrs, BPD"
                });
            }

            // Patient B: True vulnerabilities: Asthma, Newborn
            let patB_matches_filter = chk_asthma || chk_newborn;
            let patB_true_air = air_active;
            let patB_true_therm = temp_active;
            
            if (patB_matches_filter && (patB_true_air || patB_true_therm)) {
                mockPatients.push({
                    name_masked: "Mock Patient B.", patient_id: "CM-MOCK2", tambon: tambon === "All Tambon" ? "Multiple" : tambon,
                    risk_type: (patB_true_air && patB_true_therm) ? "COMBINED" : (patB_true_air ? "AIR" : "THERMAL"),
                    env_details: "Extreme values present",
                    flags: "Newborn (<= 1 yr), Asthma / AR"
                });
            }

            // Recalculate Cohorts Dynamically
            let air_count = mockPatients.filter(p => p.risk_type === 'AIR' || p.risk_type === 'COMBINED').length;
            let thermal_count = mockPatients.filter(p => p.risk_type === 'THERMAL' || p.risk_type === 'COMBINED').length;
            let combined_count = mockPatients.filter(p => p.risk_type === 'COMBINED').length;
            
            const scale = 14; 

            const mockData = {
                environment: { 
                    labels, pm25, temperature, stations: mockStations 
                },
                cohorts: {
                    air_risk_count: air_count * scale,
                    thermal_risk_count: thermal_count * scale,
                    combined_risk_count: combined_count * scale,
                    total_risk_count: (air_count + thermal_count - combined_count) * scale
                },
                admin_cohorts: {
                    air_risk_count: air_active ? 125 : 0,
                    thermal_risk_count: temp_active ? 68 : 0,
                    combined_risk_count: (air_active && temp_active) ? 27 : 0
                },
                patients: mockPatients
            };

            updateDashboardUI(mockData);
        }

        async function fetchDashboardData() {
            const prov = document.getElementById('province-select')?.value || 'Chiang Mai';
            const amphoe = document.getElementById('amphoe-select')?.value || 'All Amphoe';
            const tambon = document.getElementById('location-select')?.value || 'All Tambon';
            const startDate = document.getElementById('start-date')?.value || '2026-04-10';
            const endDate = document.getElementById('end-date')?.value || '2026-05-10';
            
            // Get checkbox states
            const chk_child_5 = document.getElementById('chk-child-5')?.checked ?? true;
            const chk_newborn = document.getElementById('chk-newborn')?.checked ?? true;
            const chk_athlete = document.getElementById('chk-athlete')?.checked ?? true;
            const chk_obesity = document.getElementById('chk-obesity')?.checked ?? true;
            const chk_underweight = document.getElementById('chk-underweight')?.checked ?? true;
            const chk_bpd = document.getElementById('chk-bpd')?.checked ?? true;
            const chk_rti = document.getElementById('chk-rti')?.checked ?? true;
            const chk_asthma = document.getElementById('chk-asthma')?.checked ?? true;
            const chk_ar = document.getElementById('chk-ar')?.checked ?? true;
            const chk_chd = document.getElementById('chk-chd')?.checked ?? true;
            const chk_fever = document.getElementById('chk-fever')?.checked ?? true;
            const chk_kidney = document.getElementById('chk-kidney')?.checked ?? true;
            const chk_neuro = document.getElementById('chk-neuro')?.checked ?? true;
            const chk_beta_blocker = document.getElementById('chk-beta-blocker')?.checked ?? true;
            const chk_antihistamine = document.getElementById('chk-antihistamine')?.checked ?? true;
            const chk_diuretic = document.getElementById('chk-diuretic')?.checked ?? true;

            const start = new Date(startDate);
            const end = new Date(endDate);
            const diffDays = Math.floor((end - start) / (1000 * 60 * 60 * 24));

            if (window.location.protocol === 'blob:' || window.location.protocol === 'data:' || window.location.protocol === 'file:') {
                console.info("Running in preview mode. Loading mock data...");
                loadMockFallback(prov, amphoe, tambon, currentMode);
                return;
            }

            try {
                const params = new URLSearchParams({
                    province: prov, amphoe: amphoe, tambon: tambon,
                    start_date: startDate, end_date: endDate, mode: currentMode,
                    chk_child_5, chk_newborn, chk_athlete, chk_obesity, chk_underweight,
                    chk_bpd, chk_rti, chk_asthma, chk_ar, chk_chd,
                    chk_fever, chk_kidney, chk_neuro, chk_beta_blocker, chk_antihistamine, chk_diuretic
                });

                const response = await fetch(`/api/data?${params.toString()}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.error) {
                    console.warn("Backend returned error:", data.error);
                    loadMockFallback(prov, amphoe, tambon);
                    return;
                }

                updateDashboardUI(data);

            } catch (error) {
                // Handle fallback with the new mode
                loadMockFallback(prov, amphoe, tambon, currentMode);
            }
        }

        // Initialize dashboard data on load
        window.addEventListener('DOMContentLoaded', () => {
            refreshPresetDropdown();
            renderActiveFilters();
            if (document.getElementById('province-select')) {
                initLocationDropdowns(); // This will trigger fetchDashboardData internally
            } else if (document.getElementById('patient-table-body') || document.getElementById('total-risk-count')) {
                fetchDashboardData();
            }
        });

        // --- 4. AI Modal Logic ---
        async function openModal(patient, condition, env) {
            document.getElementById('modalPatientName').innerText = patient;
            document.getElementById('modalCondition').innerText = condition;
            document.getElementById('modalEnv').innerText = env;
            
            const modal = document.getElementById('aiModal');
            const loading = document.getElementById('aiLoading');
            const result = document.getElementById('aiResult');
            
            modal.classList.remove('hidden');
            loading.classList.remove('hidden');
            result.classList.add('hidden');
            result.value = "";

            const apiKey = ""; // Canvas will automatically provide the API key at runtime
            const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=${apiKey}`;

            const systemPrompt = "You are a helpful AI assistant for a local health clinic in Chiang Mai, Thailand. Your task is to write a short, empathetic, and urgent SMS warning in Thai to a vulnerable patient. Advise them on what precautions to take based on their specific health conditions and the current environmental factors. Keep it under 250 characters.";
            const userPrompt = `Patient Name: ${patient}\nHealth Conditions: ${condition}\nEnvironmental Risk: ${env}\n\nPlease generate the Thai SMS.`;

            const payload = {
                contents: [{ parts: [{ text: userPrompt }] }],
                systemInstruction: { parts: [{ text: systemPrompt }] },
                generationConfig: {
                    temperature: 0.7,
                    maxOutputTokens: 150,
                }
            };

            try {
                const response = await fetch(apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();
                const generatedText = data.candidates?.[0]?.content?.parts?.[0]?.text || "ขออภัย ไม่สามารถสร้างข้อความได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง";

                loading.classList.add('hidden');
                result.classList.remove('hidden');
                result.value = generatedText.trim();
            } catch (error) {
                console.error("Error generating SMS:", error);
                loading.classList.add('hidden');
                result.classList.remove('hidden');
                result.value = "Error connecting to AI service. Please type your message manually.";
            }
        }

        function closeModal() {
            document.getElementById('aiModal').classList.add('hidden');
        }

        function sendSMS() {
            const btn = document.querySelector('#aiModal button.bg-green-600');
            if (btn) {
                const originalText = btn.innerText;
                btn.innerText = "Sent!";
                btn.classList.remove('bg-green-600', 'hover:bg-green-700');
                btn.classList.add('bg-green-800');
                setTimeout(() => {
                    closeModal();
                    btn.innerText = originalText;
                    btn.classList.add('bg-green-600', 'hover:bg-green-700');
                    btn.classList.remove('bg-green-800');
                }, 1000);
            } else {
                closeModal();
            }
        }

