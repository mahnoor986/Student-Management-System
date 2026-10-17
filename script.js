(() => {
  'use strict';

  // Change this one value if Django is served from a different local address.
  const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000/api`;
  const COURSES = ['Computer Science', 'Business Administration', 'Data Science', 'Graphic Design', 'Psychology', 'Software Engineering'];
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const els = {
    heading: $('#page-heading'), dashboard: $('#dashboard-view'), students: $('#students-view'), formPage: $('#add-student-view'),
    stats: $('#stats-grid'), recentBody: $('#recent-table-body'), recentEmpty: $('#recent-empty'), studentsBody: $('#students-table-body'),
    studentsEmpty: $('#students-empty'), emptyTitle: $('#students-empty-title'), emptyCopy: $('#students-empty-copy'), emptyAdd: $('#empty-add-button'),
    tableFooter: $('#table-footer'), search: $('#student-search'), courseFilter: $('#course-filter'), statusFilter: $('#status-filter'),
    form: $('#student-form'), formTitle: $('#form-title'), formSubtitle: $('#form-subtitle'), editId: $('#editing-id'), name: $('#full-name'),
    email: $('#email'), phone: $('#phone'), dob: $('#dob'), studentId: $('#student-id'), course: $('#course'), enrollment: $('#enrollment-date'),
    status: $('#student-status'), toastRegion: $('#toast-region'), dialog: $('#delete-dialog'), dialogCopy: $('#delete-copy'), save: $('#save-button'),
    gender: $('#gender'), address: $('#address'), department: $('#department'), departmentFilter: $('#department-filter')
  };
  let students = [];
  let departments = [];
  let summary = { total_students: 0, active_students: 0, inactive_students: 0, graduated_students: 0, total_courses: 0, recent_students: [] };
  let requestSequence = 0;
  let isSaving = false;
  let csrfToken = '';
  let currentUser = null;
  let isStaff = false;

  function escapeHTML(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
  }
  function toast(message, type = 'success') {
    const item = document.createElement('div');
    item.className = `toast ${type === 'error' ? 'error' : ''}`;
    item.setAttribute('role', type === 'error' ? 'alert' : 'status');
    item.textContent = message;
    els.toastRegion.append(item);
    window.setTimeout(() => item.remove(), type === 'error' ? 6500 : 3600);
  }
  async function apiRequest(path, options = {}) {
    let response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          ...(options.body ? { 'Content-Type': 'application/json' } : {}),
          ...(['GET', 'HEAD', 'OPTIONS'].includes((options.method || 'GET').toUpperCase()) ? {} : { 'X-CSRFToken': csrfToken }),
          ...options.headers
        }
      });
    } catch (error) {
      throw new Error(`Could not reach the Django API at ${API_BASE_URL}. Start the backend server and try again.`);
    }
    if (!response.ok) {
      if (response.status === 401) {
        window.location.replace('./login.html?next=index.html');
        throw new Error('Your session has expired. Please sign in again.');
      }
      let detail = `Request failed (${response.status}).`;
      try {
        const data = await response.json();
        detail = Object.entries(data).map(([field, messages]) => `${field === 'non_field_errors' ? 'Error' : field.replaceAll('_', ' ')}: ${Array.isArray(messages) ? messages.join(' ') : messages}`).join(' ');
      } catch { /* Keep the HTTP message when the response is not JSON. */ }
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    return response.json();
  }
  function initials(name) { return String(name || '').trim().split(/\s+/).slice(0, 2).map(part => part.charAt(0)).join('').toUpperCase() || '?'; }
  function personCell(student) {
    return `<div class="student-cell"><span class="avatar" aria-hidden="true">${escapeHTML(initials(student.name))}</span><span><span class="student-name">${escapeHTML(student.name)}</span><span class="student-email">${escapeHTML(student.email)}</span></span></div>`;
  }
  function statusCell(status) {
    const css = status === 'Active' ? 'status-active' : status === 'Graduated' ? 'status-graduated' : 'status-inactive';
    return `<span class="status-pill ${css}">${escapeHTML(status)}</span>`;
  }
  function setRowsMessage(body, tableSelector, message) {
    $(tableSelector).classList.remove('hidden');
    body.innerHTML = `<tr><td colspan="7" class="loading-cell">${escapeHTML(message)}</td></tr>`;
  }
  function renderStats() {
    const cards = [
      ['Total Students', summary.total_students, 'All database records', '♧', 'purple'],
      ['Active Students', summary.active_students, 'Currently active', '✓', 'green'],
      ['Inactive Students', summary.inactive_students, 'Not currently active', '◷', 'orange'],
      ['Graduated Students', summary.graduated_students, 'Completed studies', '✦', 'blue'],
      ['Total Courses', summary.total_courses, 'Courses represented', '▤', 'purple']
    ];
    els.stats.innerHTML = cards.map(([label, value, note, icon, color]) => `<article class="stat-card"><div class="stat-top"><span class="stat-label">${label}</span><span class="stat-icon ${color}" aria-hidden="true">${icon}</span></div><div class="stat-value">${value}</div><div class="stat-foot">${note}</div></article>`).join('');
  }
  function renderRecent() {
    const recent = summary.recent_students || [];
    els.recentEmpty.classList.toggle('hidden', recent.length > 0);
    els.recentBody.closest('.table-scroll').classList.toggle('hidden', recent.length === 0);
    els.recentBody.innerHTML = recent.map(student => `<tr><td>${personCell(student)}</td><td>${escapeHTML(student.student_id)}</td><td>${escapeHTML(student.course || '—')}</td><td>${statusCell(student.status)}</td></tr>`).join('');
  }
  function renderCourseOptions() {
    const options = [...new Set([...COURSES, ...students.map(student => student.course).filter(Boolean)])].sort((a, b) => a.localeCompare(b));
    const previousFilter = els.courseFilter.value;
    const previousCourse = els.course.value;
    els.courseFilter.innerHTML = '<option value="">All courses</option>' + options.map(course => `<option value="${escapeHTML(course)}">${escapeHTML(course)}</option>`).join('');
    els.course.innerHTML = '<option value="">Select a course</option>' + options.map(course => `<option value="${escapeHTML(course)}">${escapeHTML(course)}</option>`).join('');
    if (options.includes(previousFilter)) els.courseFilter.value = previousFilter;
    if (options.includes(previousCourse)) els.course.value = previousCourse;
    const previousDepartment = els.department.value;
    const previousDepartmentFilter = els.departmentFilter.value;
    els.department.innerHTML = '<option value="">No department</option>' + departments.map(item => `<option value="${Number(item.id)}">${escapeHTML(item.name)}</option>`).join('');
    els.departmentFilter.innerHTML = '<option value="">All departments</option>' + departments.map(item => `<option value="${Number(item.id)}">${escapeHTML(item.name)}</option>`).join('');
    if (departments.some(item => String(item.id) === previousDepartment)) els.department.value = previousDepartment;
    if (departments.some(item => String(item.id) === previousDepartmentFilter)) els.departmentFilter.value = previousDepartmentFilter;
  }
  function renderStudents() {
    renderCourseOptions();
    const noRecords = students.length === 0;
    els.studentsEmpty.classList.toggle('hidden', !noRecords);
    els.studentsBody.closest('.table-scroll').classList.toggle('hidden', noRecords);
    els.tableFooter.classList.toggle('hidden', noRecords);
    els.emptyTitle.textContent = summary.total_students ? 'No matching students' : 'No students yet';
    els.emptyCopy.textContent = summary.total_students ? 'Try changing your search or filters.' : 'Add your first student to start building your directory.';
    els.emptyAdd.classList.toggle('hidden', summary.total_students > 0 || !isStaff);
    els.studentsBody.innerHTML = students.map(student => `<tr><td>${personCell(student)}<button class="student-profile-link" type="button" data-action="profile" data-id="${Number(student.id)}">View profile</button></td><td>${escapeHTML(student.student_id)}</td><td>${escapeHTML(student.course || '—')}</td><td>${escapeHTML(student.department_name || '—')}</td><td>${escapeHTML(student.phone || '—')}</td><td>${statusCell(student.status)}</td><td>${isStaff ? `<div class="row-actions"><button class="icon-button" type="button" data-action="edit" data-id="${Number(student.id)}" aria-label="Edit ${escapeHTML(student.name)}">✎</button><button class="icon-button delete-action" type="button" data-action="delete" data-id="${Number(student.id)}" aria-label="Delete ${escapeHTML(student.name)}">⌫</button></div>` : ''}</td></tr>`).join('');
    els.tableFooter.textContent = `Showing ${students.length} ${students.length === 1 ? 'student' : 'students'} (server filtered)`;
  }
  async function loadSummary() {
    summary = await apiRequest('/students/summary/');
    renderStats(); renderRecent();
  }
  function responseItems(data) { return Array.isArray(data) ? data : (data.results || []); }
  async function loadDepartments() {
    const data = await apiRequest('/departments/');
    departments = responseItems(data);
    renderCourseOptions();
    $('#departments-table-body').innerHTML = departments.map(item => `<tr><td>${escapeHTML(item.name)}</td><td>${escapeHTML(item.code || '—')}</td><td>${escapeHTML(item.description || '—')}</td><td>${Number(item.student_count || 0)}</td><td>${isStaff ? `<div class="row-actions"><button class="icon-button" data-department-action="edit" data-id="${Number(item.id)}" type="button">Edit</button><button class="icon-button delete-action" data-department-action="delete" data-id="${Number(item.id)}" type="button">Delete</button></div>` : ''}</td></tr>`).join('');
    $('#department-message').textContent = departments.length ? '' : 'No departments have been added yet.';
  }
  async function loadAttendance() {
    try {
      const [attendanceData, studentData] = await Promise.all([
        apiRequest(`/attendance/${$('#attendance-date-filter').value ? `?date=${encodeURIComponent($('#attendance-date-filter').value)}` : ''}`),
        apiRequest('/students/')
      ]);
      const records = responseItems(attendanceData);
      const roster = responseItems(studentData);
      $('#attendance-student').innerHTML = '<option value="">Select student</option>' + roster.map(item => `<option value="${Number(item.id)}">${escapeHTML(item.name)} (${escapeHTML(item.student_id)})</option>`).join('');
      $('#attendance-table-body').innerHTML = records.map(item => `<tr><td>${escapeHTML(item.student_full_name)}</td><td>${escapeHTML(item.student_id)}</td><td>${escapeHTML(item.date)}</td><td>${statusCell(item.status)}</td><td>${isStaff ? `<button class="icon-button" type="button" data-attendance-edit="${Number(item.id)}" data-student="${Number(item.student)}" data-date="${escapeHTML(item.date)}" data-status="${escapeHTML(item.status)}">Edit</button>` : ''}</td></tr>`).join('');
      $('#attendance-empty').classList.toggle('hidden', records.length > 0);
    } catch (error) { toast(error.message, 'error'); }
  }
  async function showProfile(id) {
    try {
      const student = await apiRequest(`/students/${Number(id)}/`);
      $('#profile-title').textContent = student.name;
      const values = [
        ['Student ID', student.student_id], ['Full name', student.name], ['Email', student.email], ['Phone', student.phone],
        ['Date of birth', student.date_of_birth], ['Gender', student.gender], ['Course', student.course], ['Department', student.department_name],
        ['Enrollment date', student.enrollment_date], ['Status', student.status]
      ];
      if (isStaff && student.address) values.push(['Address', student.address]);
      $('#profile-details').innerHTML = `<dl class="profile-grid">${values.map(([label, value]) => `<div><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(value || 'Not provided')}</dd></div>`).join('')}</dl>${isStaff ? `<button class="button button-primary" type="button" data-profile-edit="${Number(student.id)}">Edit profile</button>` : ''}`;
      navigate('profile');
    } catch (error) { toast(error.message, 'error'); }
  }
  function listQuery() {
    const params = new URLSearchParams();
    if (els.search.value.trim()) params.set('search', els.search.value.trim());
    if (els.courseFilter.value) params.set('course', els.courseFilter.value);
    if (els.departmentFilter.value) params.set('department', els.departmentFilter.value);
    if (els.statusFilter.value) params.set('status', els.statusFilter.value);
    const query = params.toString();
    return query ? `?${query}` : '';
  }
  async function loadStudents({ report = true } = {}) {
    const sequence = ++requestSequence;
    els.studentsEmpty.classList.add('hidden');
    setRowsMessage(els.studentsBody, '#students-view .table-scroll', 'Loading student records…');
    try {
      const data = await apiRequest(`/students/${listQuery()}`);
      if (sequence !== requestSequence) return;
      students = Array.isArray(data) ? data : data.results;
      renderStudents();
    } catch (error) {
      if (sequence !== requestSequence) return;
      students = [];
      renderStudents();
      els.studentsEmpty.classList.remove('hidden');
      els.emptyTitle.textContent = 'Backend unavailable';
      els.emptyCopy.textContent = error.message;
      els.emptyAdd.classList.add('hidden');
      if (report) toast(error.message, 'error');
    }
  }
  async function refreshAll({ report = true } = {}) {
    try {
      await loadSummary();
      if (report) toast('Dashboard data refreshed.');
    } catch (error) {
      toast(error.message, 'error');
    }
    if (!els.students.classList.contains('hidden')) await loadStudents({ report });
  }
  function navigate(page) {
    if (!['dashboard', 'students', 'add-student', 'departments', 'attendance', 'profile'].includes(page)) page = 'dashboard';
    if (page === 'add-student' && !isStaff) { toast('Only staff members can manage student records.', 'error'); page = 'students'; }
    $$('.page-view').forEach(view => view.classList.add('hidden'));
    $(`#${page}-view`).classList.remove('hidden');
    $$('.nav-link').forEach(link => link.classList.toggle('active', link.dataset.page === page));
    els.heading.textContent = page === 'add-student' && els.editId.value ? 'Edit Student' : page === 'add-student' ? 'Add Student' : page === 'students' ? 'Students' : page === 'departments' ? 'Departments' : page === 'attendance' ? 'Attendance' : page === 'profile' ? 'Student profile' : 'Dashboard';
    $('#sidebar').classList.remove('open'); $('#menu-toggle').setAttribute('aria-expanded', 'false');
    if (page === 'students') loadStudents();
    if (page === 'departments') loadDepartments();
    if (page === 'attendance') loadAttendance();
    if (page === 'add-student') els.name.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function clearErrors() {
    $$('.field-error').forEach(item => { item.textContent = ''; });
    $$('.field input,.field select').forEach(field => field.removeAttribute('aria-invalid'));
  }
  function showError(field, errorId, message) { field.setAttribute('aria-invalid', 'true'); $('#' + errorId).textContent = message; }
  function startAdd() {
    if (!isStaff) { toast('Only staff members can add students.', 'error'); navigate('students'); return; }
    els.form.reset(); els.editId.value = ''; clearErrors(); els.status.value = 'Active';
    els.enrollment.value = new Date().toISOString().slice(0, 10);
    els.formTitle.textContent = 'Add Student'; els.formSubtitle.textContent = 'Add a new student to your directory.';
    els.save.innerHTML = 'Save Student <span aria-hidden="true">→</span>';
    renderCourseOptions(); navigate('add-student');
  }
  async function startEdit(id) {
    if (!isStaff) { toast('Only staff members can edit student records.', 'error'); return; }
    clearErrors();
    try {
      const student = await apiRequest(`/students/${Number(id)}/`);
      renderCourseOptions(); els.editId.value = String(student.id);
      els.name.value = student.name; els.email.value = student.email; els.phone.value = student.phone || '';
      els.dob.value = student.date_of_birth || ''; els.gender.value = student.gender || ''; els.address.value = student.address || ''; els.department.value = student.department ? String(student.department) : ''; els.studentId.value = student.student_id; els.course.value = student.course || '';
      els.enrollment.value = student.enrollment_date || ''; els.status.value = student.status;
      els.formTitle.textContent = 'Edit Student'; els.formSubtitle.textContent = `Update ${student.name}’s student record.`;
      els.save.innerHTML = 'Save Changes <span aria-hidden="true">→</span>';
      navigate('add-student');
    } catch (error) { toast(error.message, 'error'); }
  }
  function validateForm() {
    clearErrors(); let valid = true;
    const name = els.name.value.trim(); const email = els.email.value.trim();
    if (!name) { showError(els.name, 'name-error', 'Please enter the student’s full name.'); valid = false; }
    else if (name.split(/\s+/).length < 2) { showError(els.name, 'name-error', 'Please enter both a first and last name.'); valid = false; }
    if (!email) { showError(els.email, 'email-error', 'Please enter an email address.'); valid = false; }
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { showError(els.email, 'email-error', 'Enter a valid email address, like name@example.com.'); valid = false; }
    if (!els.course.value) { showError(els.course, 'course-error', 'Please select a course.'); valid = false; }
    if (!els.studentId.value.trim() && !els.editId.value) els.studentId.value = `STU-${Date.now().toString().slice(-8)}`;
    return valid;
  }
  function splitName(name) {
    const parts = name.trim().split(/\s+/);
    return { first_name: parts.shift() || '', last_name: parts.join(' ') || '-' };
  }
  async function submitForm(event) {
    event.preventDefault();
    if (isSaving) return;
    if (!validateForm()) { $('.field [aria-invalid="true"]')?.focus(); return; }
    const names = splitName(els.name.value);
    const payload = { ...names, student_id: els.studentId.value.trim(), email: els.email.value.trim(), phone: els.phone.value.trim(), course: els.course.value, date_of_birth: els.dob.value || null, enrollment_date: els.enrollment.value || undefined, status: els.status.value, gender: els.gender.value, address: els.address.value.trim(), department: els.department.value || null };
    const editing = Boolean(els.editId.value);
    const endpoint = editing ? `/students/${Number(els.editId.value)}/` : '/students/';
    isSaving = true; els.save.disabled = true; els.save.textContent = 'Saving…';
    try {
      await apiRequest(endpoint, { method: editing ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      toast(editing ? 'Student record updated.' : 'Student added successfully.');
      navigate('students');
      loadSummary().catch(error => toast(`Student saved, but dashboard refresh failed: ${error.message}`, 'error'));
    } catch (error) {
      toast(error.message, 'error');
      showBackendErrors(error.message);
    } finally {
      isSaving = false; els.save.disabled = false;
      els.save.innerHTML = editing ? 'Save Changes <span aria-hidden="true">→</span>' : 'Save Student <span aria-hidden="true">→</span>';
    }
  }
  function showBackendErrors(message) {
    const fields = [['first name', els.name, 'name-error'], ['last name', els.name, 'name-error'], ['email', els.email, 'email-error'], ['student id', els.studentId, 'id-error'], ['course', els.course, 'course-error']];
    for (const [field, input, errorId] of fields) {
      const match = message.match(new RegExp(`${field}:\\s*([^.]*(?:\\.[^.]*)?)`, 'i'));
      if (match) showError(input, errorId, match[1].trim());
    }
  }
  let pendingDeleteId = null;
  function requestDelete(id) {
    if (!isStaff) { toast('Only staff members can delete student records.', 'error'); return; }
    const student = students.find(item => String(item.id) === String(id)); if (!student) return;
    pendingDeleteId = Number(id); els.dialogCopy.textContent = `${student.name}’s record will be permanently removed from the database.`;
    els.dialog.showModal();
  }
  async function confirmDelete(event) {
    if (event.submitter?.value !== 'delete') { pendingDeleteId = null; return; }
    event.preventDefault(); if (!pendingDeleteId) return;
    const id = pendingDeleteId; pendingDeleteId = null;
    const button = $('#confirm-delete'); button.disabled = true; button.textContent = 'Deleting…';
    try {
      await apiRequest(`/students/${id}/`, { method: 'DELETE' });
      els.dialog.close(); toast('Student deleted.');
      await loadSummary().catch(error => toast(`Student deleted, but dashboard refresh failed: ${error.message}`, 'error'));
      await loadStudents({ report: false });
    } catch (error) { toast(error.message, 'error'); }
    finally { button.disabled = false; button.textContent = 'Delete student'; }
  }

  $$('.nav-link').forEach(link => link.addEventListener('click', event => { event.preventDefault(); if (link.dataset.page === 'add-student') startAdd(); else navigate(link.dataset.page); history.replaceState(null, '', `#${link.dataset.page}`); }));
  $$('[data-go]').forEach(button => button.addEventListener('click', () => { if (button.dataset.go === 'add-student') startAdd(); else navigate(button.dataset.go); history.replaceState(null, '', `#${button.dataset.go}`); }));
  $('#menu-toggle').addEventListener('click', event => { const open = $('#sidebar').classList.toggle('open'); event.currentTarget.setAttribute('aria-expanded', String(open)); });
  els.form.addEventListener('submit', submitForm);
  let searchTimer;
  els.search.addEventListener('input', () => { window.clearTimeout(searchTimer); searchTimer = window.setTimeout(() => loadStudents(), 250); });
  els.courseFilter.addEventListener('change', () => loadStudents()); els.statusFilter.addEventListener('change', () => loadStudents());
  els.studentsBody.addEventListener('click', event => {
    const button = event.target.closest('[data-action]'); if (!button) return;
    if (button.dataset.action === 'edit') startEdit(button.dataset.id);
    if (button.dataset.action === 'delete') requestDelete(button.dataset.id);
    if (button.dataset.action === 'profile') showProfile(button.dataset.id);
  });
  els.dialog.addEventListener('submit', confirmDelete);
  els.departmentFilter.addEventListener('change', () => loadStudents());
  $('#department-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!isStaff) return;
    const id = $('#department-edit-id').value;
    const payload = { name: $('#department-name').value.trim(), code: $('#department-code').value.trim(), description: $('#department-description').value.trim() };
    try {
      await apiRequest(id ? `/departments/${Number(id)}/` : '/departments/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(payload) });
      event.currentTarget.reset(); $('#department-edit-id').value = ''; $('#department-cancel').classList.add('hidden');
      toast(id ? 'Department updated.' : 'Department created.'); await loadDepartments();
    } catch (error) { toast(error.message, 'error'); }
  });
  $('#departments-table-body').addEventListener('click', async event => {
    const button = event.target.closest('[data-department-action]'); if (!button) return;
    const department = departments.find(item => String(item.id) === button.dataset.id); if (!department) return;
    if (button.dataset.departmentAction === 'edit') {
      $('#department-edit-id').value = department.id; $('#department-name').value = department.name; $('#department-code').value = department.code || ''; $('#department-description').value = department.description || ''; $('#department-cancel').classList.remove('hidden'); $('#department-name').focus();
    } else if (window.confirm(`Delete ${department.name}? Departments with assigned students cannot be deleted.`)) {
      try { await apiRequest(`/departments/${Number(department.id)}/`, { method: 'DELETE' }); toast('Department deleted.'); await loadDepartments(); }
      catch (error) { toast(error.message, 'error'); }
    }
  });
  $('#department-cancel').addEventListener('click', () => { $('#department-form').reset(); $('#department-edit-id').value = ''; $('#department-cancel').classList.add('hidden'); });
  $('#attendance-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!isStaff) return;
    const id = $('#attendance-edit-id').value;
    const payload = { student: Number($('#attendance-student').value), date: $('#attendance-date').value, status: $('#attendance-status').value };
    try { await apiRequest(id ? `/attendance/${Number(id)}/` : '/attendance/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(payload) }); toast(id ? 'Attendance updated.' : 'Attendance recorded.'); event.currentTarget.reset(); $('#attendance-edit-id').value = ''; $('#attendance-date').value = new Date().toISOString().slice(0, 10); $('#attendance-cancel').classList.add('hidden'); await loadAttendance(); }
    catch (error) { toast(error.message, 'error'); }
  });
  $('#attendance-table-body').addEventListener('click', event => {
    const button = event.target.closest('[data-attendance-edit]'); if (!button || !isStaff) return;
    $('#attendance-edit-id').value = button.dataset.attendanceEdit; $('#attendance-student').value = button.dataset.student; $('#attendance-date').value = button.dataset.date; $('#attendance-status').value = button.dataset.status; $('#attendance-cancel').classList.remove('hidden');
  });
  $('#attendance-cancel').addEventListener('click', () => { $('#attendance-form').reset(); $('#attendance-edit-id').value = ''; $('#attendance-date').value = new Date().toISOString().slice(0, 10); $('#attendance-cancel').classList.add('hidden'); });
  $('#attendance-date-filter').addEventListener('change', loadAttendance);
  $('#attendance-load').addEventListener('click', () => { $('#attendance-date-filter').value = ''; loadAttendance(); });
  $('#profile-details').addEventListener('click', event => { const button = event.target.closest('[data-profile-edit]'); if (button) startEdit(button.dataset.profileEdit); });
  $('#refresh-data').addEventListener('click', () => refreshAll());
  async function getCsrfToken() {
    const response = await fetch(`${API_BASE_URL}/auth/csrf/`, { credentials: 'include', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Could not initialize secure session protection.');
    const data = await response.json();
    csrfToken = data.csrfToken;
  }
  async function initializeDashboard() {
    const gateMessage = $('#auth-gate-message');
    try {
      await getCsrfToken();
      const response = await fetch(`${API_BASE_URL}/auth/me/`, { credentials: 'include', headers: { Accept: 'application/json' } });
      if (response.status === 401 || response.status === 403) {
        window.location.replace('./login.html?next=index.html');
        return;
      }
      if (!response.ok) throw new Error(`Session check failed (${response.status}).`);
      const result = await response.json();
      currentUser = result.user;
      isStaff = Boolean(currentUser.is_staff);
      $('#auth-user').textContent = `${currentUser.username} · ${isStaff ? 'Staff' : 'Read only'}`;
      $$('[data-role="staff"]').forEach(control => control.classList.toggle('hidden', !isStaff));
      $('#auth-gate').classList.add('hidden');
      $('#app-shell').classList.remove('hidden');
      $('#today-label').textContent = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date());
      departments = responseItems(await apiRequest('/departments/'));
      $('#attendance-date').value = new Date().toISOString().slice(0, 10);
      renderCourseOptions();
      const initialPage = location.hash.slice(1);
      navigate(['students', 'departments', 'attendance'].includes(initialPage) ? initialPage : initialPage === 'add-student' && isStaff ? 'add-student' : 'dashboard');
      await loadSummary();
    } catch (error) {
      gateMessage.textContent = `${error.message} Check that Django is running and retry.`;
      $('#auth-retry').classList.remove('hidden');
      $('#auth-login-link').classList.remove('hidden');
    }
  }
  $('#auth-retry').addEventListener('click', () => {
    $('#auth-retry').classList.add('hidden');
    $('#auth-login-link').classList.add('hidden');
    $('#auth-gate-message').textContent = 'Connecting securely to your student portal…';
    initializeDashboard();
  });
  $('#logout-button').addEventListener('click', async event => {
    const button = event.currentTarget; button.disabled = true; button.textContent = 'Signing out…';
    try {
      await apiRequest('/auth/logout/', { method: 'POST' });
    } catch (error) {
      toast(error.message, 'error'); button.disabled = false; button.textContent = 'Log out'; return;
    }
    window.location.replace('./login.html');
  });
  initializeDashboard();
})();
