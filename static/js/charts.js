/**
 * charts.js
 * ==========
 * Chart.js configurations for the Pack Proof dashboard.
 * 
 * Charts:
 * - Compliance Distribution (doughnut)
 * - Toxicity Risk Analysis (horizontal bar)
 */

function initComplianceChart(compliant, warnings, nonCompliant, rescan) {
    const ctx = document.getElementById('complianceChart');
    if (!ctx) return;

    const total = compliant + warnings + nonCompliant + rescan;
    if (total === 0) {
        // Show empty state
        ctx.parentElement.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94A3B8;font-size:0.9rem;">No scan data yet</div>';
        return;
    }

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Compliant', 'Warnings', 'Non-Compliant', 'Rescan'],
            datasets: [{
                data: [compliant, warnings, nonCompliant, rescan],
                backgroundColor: [
                    '#10B981',
                    '#F59E0B',
                    '#EF4444',
                    '#94A3B8',
                ],
                borderColor: [
                    '#059669',
                    '#D97706',
                    '#DC2626',
                    '#64748B',
                ],
                borderWidth: 2,
                hoverBorderWidth: 3,
                hoverOffset: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '68%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 16,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        font: {
                            family: "'Inter', sans-serif",
                            size: 11,
                            weight: '500',
                        },
                        color: '#64748B',
                    },
                },
                tooltip: {
                    backgroundColor: '#0F1B2D',
                    titleFont: { family: "'Inter', sans-serif", size: 12, weight: '600' },
                    bodyFont: { family: "'Inter', sans-serif", size: 11 },
                    padding: 12,
                    cornerRadius: 8,
                    displayColors: true,
                    callbacks: {
                        label: function (context) {
                            const value = context.parsed;
                            const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return ` ${context.label}: ${value} (${pct}%)`;
                        },
                    },
                },
            },
            animation: {
                animateScale: true,
                animateRotate: true,
                duration: 1200,
                easing: 'easeOutQuart',
            },
        },
    });
}


function initToxicityChart(safe, caution, notRecommended) {
    const ctx = document.getElementById('toxicityChart');
    if (!ctx) return;

    const total = safe + caution + notRecommended;
    if (total === 0) {
        ctx.parentElement.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#94A3B8;font-size:0.9rem;">No toxicity data yet</div>';
        return;
    }

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Safe', 'Use with Caution', 'Not Recommended'],
            datasets: [{
                label: 'Products',
                data: [safe, caution, notRecommended],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(239, 68, 68, 0.8)',
                ],
                borderColor: [
                    '#059669',
                    '#D97706',
                    '#DC2626',
                ],
                borderWidth: 1,
                borderRadius: 6,
                borderSkipped: false,
                barPercentage: 0.6,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0F1B2D',
                    titleFont: { family: "'Inter', sans-serif", size: 12, weight: '600' },
                    bodyFont: { family: "'Inter', sans-serif", size: 11 },
                    padding: 12,
                    cornerRadius: 8,
                },
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                        font: { family: "'Inter', sans-serif", size: 11 },
                        color: '#94A3B8',
                    },
                    grid: {
                        color: 'rgba(226, 232, 240, 0.5)',
                    },
                },
                y: {
                    ticks: {
                        font: { family: "'Inter', sans-serif", size: 11, weight: '500' },
                        color: '#64748B',
                    },
                    grid: { display: false },
                },
            },
            animation: {
                duration: 1000,
                easing: 'easeOutQuart',
            },
        },
    });
}
