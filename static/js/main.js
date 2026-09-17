/**
 * main.js
 * ========
 * Client-side interactivity for Pack Proof.
 * 
 * Features:
 * - Drag-and-drop file upload with preview
 * - Sidebar toggle (desktop + mobile)
 * - Toast notifications
 * - File upload preview grid
 */

document.addEventListener('DOMContentLoaded', function () {

    // ── Sidebar Toggle ───────────────────────────────────────────────────

    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mobileToggle = document.getElementById('mobileToggle');

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('collapsed');
            document.querySelector('.main-content').classList.toggle('expanded');
        });
    }

    if (mobileToggle) {
        mobileToggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
        });

        // Close sidebar on outside click (mobile)
        document.addEventListener('click', function (e) {
            if (sidebar.classList.contains('open') &&
                !sidebar.contains(e.target) &&
                !mobileToggle.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
    }


    // ── Drag & Drop Upload ───────────────────────────────────────────────

    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const previewGrid = document.getElementById('previewGrid');

    if (uploadZone && fileInput) {
        // Click to open file dialog
        uploadZone.addEventListener('click', function () {
            fileInput.click();
        });

        // Drag events
        uploadZone.addEventListener('dragover', function (e) {
            e.preventDefault();
            uploadZone.classList.add('drag-over');
        });

        uploadZone.addEventListener('dragleave', function () {
            uploadZone.classList.remove('drag-over');
        });

        uploadZone.addEventListener('drop', function (e) {
            e.preventDefault();
            uploadZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                showPreviews(e.dataTransfer.files);
            }
        });

        // File input change
        fileInput.addEventListener('change', function () {
            if (fileInput.files.length > 0) {
                showPreviews(fileInput.files);
            }
        });
    }

    function showPreviews(files) {
        if (!previewGrid) return;
        previewGrid.innerHTML = '';
        Array.from(files).forEach(function (file) {
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.className = 'preview-thumb';
                    img.alt = file.name;
                    img.title = file.name;
                    previewGrid.appendChild(img);
                };
                reader.readAsDataURL(file);
            }
        });

        // Update upload zone text
        if (uploadZone) {
            const uploadText = uploadZone.querySelector('.upload-text');
            if (uploadText) {
                uploadText.textContent = files.length + ' file(s) selected';
            }
        }
    }


    // ── Flash Message Auto-Dismiss ───────────────────────────────────────

    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(function (flash) {
        setTimeout(function () {
            flash.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            setTimeout(function () { flash.remove(); }, 500);
        }, 8000);
    });


    // ── Animate numbers on dashboard ─────────────────────────────────────

    document.querySelectorAll('.kpi-value').forEach(function (el) {
        const target = parseFloat(el.textContent);
        if (isNaN(target)) return;

        const suffix = el.textContent.replace(/[\d.]/g, '');
        const duration = 1000;
        const step = target / (duration / 16);
        let current = 0;

        function animate() {
            current += step;
            if (current >= target) {
                el.textContent = (Number.isInteger(target) ? target : target.toFixed(1)) + suffix;
                return;
            }
            el.textContent = (Number.isInteger(target) ? Math.floor(current) : current.toFixed(1)) + suffix;
            requestAnimationFrame(animate);
        }
        animate();
    });

});
