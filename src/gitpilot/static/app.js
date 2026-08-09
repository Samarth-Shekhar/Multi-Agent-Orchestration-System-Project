document.addEventListener('DOMContentLoaded', () => {
    const runForm = document.getElementById('runForm');
    const runBtn = document.getElementById('runBtn');
    const repoUrlInput = document.getElementById('repoUrl');
    const issueNumberInput = document.getElementById('issueNumber');
    const serverStatus = document.getElementById('serverStatus');
    const serverStatusText = document.getElementById('serverStatusText');
    const pipelineGraph = document.getElementById('pipelineGraph');
    const feedList = document.getElementById('feedList');
    const agentOutput = document.getElementById('agentOutput');
    const summaryRunId = document.getElementById('summaryRunId');
    const summaryStartedAt = document.getElementById('summaryStartedAt');
    const summaryRepo = document.getElementById('summaryRepo');
    const summaryIssue = document.getElementById('summaryIssue');
    const summaryBranch = document.getElementById('summaryBranch');
    const summaryStatus = document.getElementById('summaryStatus');
    const runStatusValue = document.getElementById('runStatusValue');
    const formError = document.getElementById('formError');
    const currentStage = document.getElementById('currentStage');
    const progressValue = document.getElementById('progressValue');
    const progressValueSmall = document.getElementById('progressValueSmall');
    const progressBar = document.getElementById('progressBar');
    const runIdValue = document.getElementById('runIdValue');
    const repairValue = document.getElementById('repairValue');
    const repoValue = document.getElementById('repoValue');
    const elapsedValue = document.getElementById('elapsedValue');
    const activityElapsedValue = document.getElementById('activityElapsedValue');
    const issueContent = document.getElementById('issueContent');
    const planContent = document.getElementById('planContent');
    const diffContent = document.getElementById('diffContent');
    const testContent = document.getElementById('testContent');
    const reviewContent = document.getElementById('reviewContent');
    const prContent = document.getElementById('prContent');
    const summaryCard = document.getElementById('summaryCard');
    const insightList = document.getElementById('insightList');
    const drawer = document.getElementById('agentDrawer');
    const drawerContent = document.getElementById('drawerContent');
    const themeToggle = document.getElementById('themeToggle');
    const pageTitle = document.getElementById('pageTitle');
    const navItems = document.querySelectorAll('.nav-item');

    const agentDefs = [
        {
            key: 'issue_loader',
            number: '01',
            name: 'Issue Loader',
            role: 'Issue Intake Agent',
            description: 'Reads the GitHub issue and extracts requirements, constraints and expected behavior.',
            avatar: '/static/images/agents/issue_loader.svg',
            running: 'Parsing issue requirements...',
            completed: 'Loaded issue details and acceptance criteria.'
        },
        {
            key: 'code_reader',
            number: '02',
            name: 'Code Reader',
            role: 'Repository Intelligence Agent',
            description: 'Explores repository structure and retrieves code relevant to the issue.',
            avatar: '/static/images/agents/code_reader.svg',
            running: 'Searching repository...',
            completed: 'Analyzed repository structure and retrieved relevant files.'
        },
        {
            key: 'planner',
            number: '03',
            name: 'Planner',
            role: 'Solution Architect',
            description: 'Determines root cause and creates the implementation and testing strategy.',
            avatar: '/static/images/agents/planner.svg',
            running: 'Designing implementation plan...',
            completed: 'Created an implementation plan.'
        },
        {
            key: 'research_agent',
            number: '04',
            name: 'Researcher',
            role: 'Technical Research Agent',
            description: 'Investigates additional code patterns and dependencies when a task requires deeper analysis.',
            avatar: '/static/images/agents/researcher.svg',
            running: 'Researching dependency patterns...',
            completed: 'Collected additional implementation context.'
        },
        {
            key: 'code_writer',
            number: '05',
            name: 'Code Writer',
            role: 'Implementation Agent',
            description: 'Generates targeted code modifications based on the approved plan.',
            avatar: '/static/images/agents/code_writer.svg',
            running: 'Implementing fix...',
            completed: 'Prepared the patch.'
        },
        {
            key: 'test_writer',
            number: '06',
            name: 'Test Writer',
            role: 'Test Engineering Agent',
            description: 'Creates regression tests and validates expected behavior.',
            avatar: '/static/images/agents/test_writer.svg',
            running: 'Writing regression tests...',
            completed: 'Generated regression tests.'
        },
        {
            key: 'test_runner',
            number: '07',
            name: 'Test Runner',
            role: 'Sandbox Validation Agent',
            description: 'Executes tests inside an isolated environment.',
            avatar: '/static/images/agents/test_runner.svg',
            running: 'Executing test suite in sandbox...',
            completed: 'Executed repository tests.'
        },
        {
            key: 'reviewer',
            number: '08',
            name: 'Reviewer',
            role: 'Code Review Agent',
            description: 'Reviews the generated patch for correctness, security and issue alignment.',
            avatar: '/static/images/agents/reviewer.svg',
            running: 'Reviewing generated changes...',
            completed: 'Completed a review.'
        },
        {
            key: 'pr_opener',
            number: '09',
            name: 'PR Opener',
            role: 'GitHub Delivery Agent',
            description: 'Creates the branch and prepares or opens the pull request.',
            avatar: '/static/images/agents/pr_opener.svg',
            running: 'Preparing PR delivery...',
            completed: 'Prepared the pull request.'
        }
    ];

    let activeRunId = null;
    let intervalHandle = null;

    function setStatus(online) {
        if (online) {
            serverStatus.classList.add('online');
            serverStatusText.textContent = 'Server ready';
        } else {
            serverStatus.classList.remove('online');
            serverStatusText.textContent = 'Server offline';
        }
    }

    function resetUI() {
        currentStage.textContent = 'Waiting for execution';
        progressValue.textContent = '0 / 9 agents';
        progressBar.style.width = '0%';
        runIdValue.textContent = '—';
        progressValueSmall.textContent = '0%';
        repairValue.textContent = '0 / 3';
        repoValue.textContent = '—';
        elapsedValue.textContent = '—';
        issueContent.innerHTML = '<div class="muted">No workflow running.</div>';
        agentOutput.textContent = 'Awaiting agent logs...';
        summaryRunId.textContent = '—';
        summaryStartedAt.textContent = '—';
        summaryRepo.textContent = '—';
        summaryIssue.textContent = '—';
        summaryBranch.textContent = '—';
        summaryStatus.textContent = 'Idle';
        runStatusValue.textContent = 'Idle';
        activityElapsedValue.textContent = '00:00:00';
        planContent.innerHTML = '<div class="muted">Enter a GitHub repository and issue number to start the multi-agent pipeline.</div>';
        diffContent.textContent = 'No diff yet.';
        testContent.textContent = 'No test output yet.';
        reviewContent.innerHTML = '<div class="muted">Waiting for review</div>';
        prContent.innerHTML = '<div class="muted">No PR created yet.</div>';
        summaryCard.innerHTML = '<div class="muted">Run a workflow to see the summary.</div>';
        insightList.innerHTML = '';
        feedList.innerHTML = '<div class="feed-placeholder">Waiting for workflow activity…</div>';
        pipelineGraph.innerHTML = '';
        renderPipeline([]);
    }

    function clearFormInputs() {
        if (repoUrlInput) {
            repoUrlInput.value = '';
            repoUrlInput.defaultValue = '';
            repoUrlInput.autocomplete = 'off';
            repoUrlInput.autocorrect = 'off';
            repoUrlInput.autocapitalize = 'off';
            repoUrlInput.spellcheck = false;
        }
        if (issueNumberInput) {
            issueNumberInput.value = '';
            issueNumberInput.defaultValue = '';
            issueNumberInput.autocomplete = 'off';
            issueNumberInput.autocorrect = 'off';
            issueNumberInput.autocapitalize = 'off';
            issueNumberInput.spellcheck = false;
        }
    }

    function renderPipeline(logs) {
        const statuses = {};
        const completed = new Set();
        const running = new Set();
        const skipped = new Set();

        logs.forEach((entry) => {
            const message = entry.message || entry.status || '';
            const node = entry.node || '';
            if (node && entry.status === 'running') {
                running.add(node);
            }
            if (message.includes('loaded') || message.includes('scanned') || message.includes('created') || message.includes('generated') || message.includes('PASSED') || message.includes('APPROVED') || message.includes('completed')) {
                completed.add(node || 'workflow');
            }
            if (message.includes('skipped') || message.includes('unnecessary')) {
                skipped.add(node || 'research_agent');
            }
        });

        const pending = agentDefs.filter((agent) => !completed.has(agent.key) && !running.has(agent.key) && !skipped.has(agent.key));
        const order = [...agentDefs].filter((agent) => agent.key !== 'research_agent');
        const research = agentDefs.find((agent) => agent.key === 'research_agent');

        const nodes = [];
        order.forEach((agent, index) => {
            let status = 'waiting';
            let activity = agent.running;
            if (running.has(agent.key)) {
                status = 'running';
            } else if (completed.has(agent.key)) {
                status = 'success';
            } else if (skipped.has(agent.key)) {
                status = 'skipped';
            }
            nodes.push({
                ...agent,
                status,
                activity: status === 'success' ? agent.completed : status === 'running' ? agent.running : status === 'skipped' ? 'Skipped — planner classified the issue as simple.' : 'Waiting for execution',
            });
        });

        if (research) {
            nodes.splice(3, 0, {
                ...research,
                status: skipped.has(research.key) ? 'skipped' : 'waiting',
                activity: skipped.has(research.key) ? 'Planner classified this issue as simple. Additional research was unnecessary.' : 'Waiting for execution',
            });
        }

        pipelineGraph.innerHTML = nodes.map((agent, index) => {
            const isResearch = agent.key === 'research_agent';
            const prev = nodes[index - 1];
            const connector = index > 0 ? `<div class="pipeline-connector ${prev?.status || 'waiting'}"></div>` : '';
            const badgeLabel = agent.status === 'running' ? 'In progress' : agent.status === 'success' ? 'Complete' : agent.status === 'skipped' ? 'Skipped' : 'Waiting';
            return `
                <div class="pipeline-column ${agent.status}">
                    ${connector}
                    <div class="connector-badge"><span></span>${badgeLabel}</div>
                    <button class="agent-card ${agent.status}" type="button" data-agent="${agent.key}">
                        <img src="${agent.avatar}" alt="${agent.name}" class="agent-avatar">
                        <div class="agent-number">${agent.number}</div>
                        <div class="agent-name">${agent.name}</div>
                        <div class="agent-role">${agent.role}</div>
                        <div class="agent-status ${agent.status}">${agent.status.toUpperCase()}</div>
                        <div class="agent-activity">${escapeHtml(agent.activity)}</div>
                    </button>
                </div>
            `;
        }).join('');
    }

    function updateFeed(events) {
        const feed = (events || []).slice(-12).reverse();
        if (!feed.length) {
            feedList.innerHTML = '<div class="feed-placeholder">Waiting for workflow activity…</div>';
            agentOutput.textContent = 'Awaiting agent logs...';
            return;
        }

        feedList.innerHTML = feed.map((entry) => {
            const message = entry.message || entry.status || 'Event received';
            const time = new Date((entry.timestamp || Date.now() / 1000) * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            return `<div class="feed-item"><div class="feed-time">${time}</div><div class="feed-message">${escapeHtml(message)}</div></div>`;
        }).join('');

        agentOutput.textContent = feed.slice(0, 8).map((entry) => {
            const time = new Date((entry.timestamp || Date.now() / 1000) * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            return `[${time}] ${entry.message || entry.status || 'Event received'}`;
        }).join('\n');
    }

    function updateResults(state) {
        const issue = state.issue || {};
        const plan = state.plan || {};
        const testResults = state.test_results || {};
        const reviewFeedback = state.review_feedback || {};
        const patch = state.patch || '';
        summaryRunId.textContent = activeRunId || '—';
        summaryStartedAt.textContent = new Date((state.started_at || Date.now() / 1000) * 1000).toLocaleString();
        summaryRepo.textContent = state.repository_url || '—';
        summaryIssue.textContent = issue.title ? `#${issue.number}: ${issue.title}` : '—';
        summaryBranch.textContent = state.branch_name || '—';
        summaryStatus.textContent = state.status ? state.status.replace(/_/g, ' ') : 'Idle';
        runStatusValue.textContent = state.status ? state.status.replace(/_/g, ' ') : 'Idle';

        issueContent.innerHTML = `<div class="result-stack"><strong>#${issue.number || '—'} ${escapeHtml(issue.title || 'No issue loaded')}</strong><p>${escapeHtml(issue.body || 'Issue details will appear here.')}</p></div>`;

        planContent.innerHTML = `<div class="result-stack"><p><strong>Summary:</strong> ${escapeHtml(plan.summary || 'Waiting for plan')}</p><p><strong>Complexity:</strong> ${escapeHtml(state.complexity || 'simple')}</p><p><strong>Risk:</strong> ${escapeHtml(plan.risk_level || 'low')}</p><p><strong>Files:</strong> ${(plan.files_to_modify || []).join(', ') || '—'}</p></div>`;

        diffContent.textContent = patch || 'No diff yet.';

        const testSummary = testResults.passed ? '✓ Passed' : '✗ Failed';
        testContent.textContent = testResults.stdout || testResults.stderr || `${testSummary}\nNo output available yet.`;

        reviewContent.innerHTML = `<div class="result-stack"><strong>${reviewFeedback.approved ? '✓ APPROVED' : '• CHANGES REQUESTED'}</strong><p>${escapeHtml(reviewFeedback.summary || 'Waiting for review')}</p></div>`;

        prContent.innerHTML = `<div class="result-stack"><p><strong>Branch:</strong> ${escapeHtml(state.branch_name || '—')}</p><p><strong>PR:</strong> ${escapeHtml(state.pr_url || 'Dry run active')}</p></div>`;

        summaryCard.innerHTML = `
            <div class="summary-box">
                <div><strong>Issue</strong><div>${escapeHtml(issue.title || '—')}</div></div>
                <div><strong>Status</strong><div>${escapeHtml(state.status || 'pending')}</div></div>
                <div><strong>Agents</strong><div>${(state.execution_log || []).filter((entry) => entry.includes('starting') || entry.includes('loaded') || entry.includes('generated') || entry.includes('PASSED') || entry.includes('APPROVED')).length} / 9</div></div>
                <div><strong>Tests</strong><div>${testResults.passed ? 'Passed' : 'Pending'}</div></div>
            </div>
        `;

        insightList.innerHTML = `
            <div class="insight-item"><strong>Suggested Improvement</strong><p>Increase test coverage for edge cases and error handling.</p></div>
            <div class="insight-item"><strong>Suggested Improvement</strong><p>Improve repository context retrieval by reducing irrelevant files.</p></div>
            <div class="insight-item"><strong>Suggested Improvement</strong><p>Add integration coverage for the full workflow loop.</p></div>
        `;
    }

    function updateProgress(state) {
        const executionLog = state.execution_log || [];
        const completedCount = executionLog.filter((entry) => entry.includes('loaded') || entry.includes('scanned') || entry.includes('generated') || entry.includes('PASSED') || entry.includes('APPROVED') || entry.includes('created') || entry.includes('completed')).length;
        const percent = Math.min(100, Math.round((completedCount / 9) * 100));
        progressBar.style.width = `${percent}%`;
        progressValue.textContent = `${Math.max(1, Math.min(9, completedCount))} / 9 agents`;
        progressValueSmall.textContent = `${percent}%`;
        currentStage.textContent = executionLog[executionLog.length - 1] ? executionLog[executionLog.length - 1] : 'Waiting for execution';
        runIdValue.textContent = activeRunId || '—';
        summaryRunId.textContent = activeRunId || '—';
        runStatusValue.textContent = state.status ? state.status.replace(/_/g, ' ') : 'Idle';
        repairValue.textContent = `${state.attempt_count || 0} / ${state.max_attempts || 3}`;
        repoValue.textContent = state.repository_url || '—';
        summaryRepo.textContent = state.repository_url || '—';
        const startedAt = state.execution_log?.[0] ? new Date().toLocaleTimeString() : '—';
        elapsedValue.textContent = startedAt;
        activityElapsedValue.textContent = startedAt;
        summaryStartedAt.textContent = state.execution_log?.[0] ? new Date((state.execution_log[0].timestamp || Date.now() / 1000) * 1000).toLocaleString() : '—';
        summaryStatus.textContent = state.status ? state.status.replace(/_/g, ' ') : 'Idle';
    }

    function openDrawer(agentKey) {
        const agent = agentDefs.find((item) => item.key === agentKey);
        if (!agent) return;
        drawerContent.innerHTML = `
            <div class="drawer-header">
                <img src="${agent.avatar}" alt="${agent.name}" class="drawer-avatar">
                <div>
                    <div class="eyebrow">Agent Detail</div>
                    <h3>${agent.name}</h3>
                </div>
            </div>
            <p class="drawer-role">${agent.role}</p>
            <p>${agent.description}</p>
            <div class="drawer-section">
                <h4>What this agent does</h4>
                <p>${agent.description}</p>
            </div>
            <div class="drawer-section">
                <h4>Current status</h4>
                <p>${agent.running}</p>
            </div>
        `;
        drawer.classList.add('open');
        drawer.setAttribute('aria-hidden', 'false');
    }

    function closeDrawer() {
        drawer.classList.remove('open');
        drawer.setAttribute('aria-hidden', 'true');
    }

    async function checkHealth() {
        try {
            const res = await fetch('/health');
            const data = await res.json();
            setStatus(data.status === 'ok');
        } catch (error) {
            setStatus(false);
        }
    }

    runForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        formError.textContent = '';
        const repoUrl = document.getElementById('repoUrl').value.trim();
        const issueNumber = parseInt(document.getElementById('issueNumber').value, 10);
        const dryRun = document.getElementById('dryRun').checked;

        if (!repoUrl || !issueNumber) {
            formError.textContent = 'Please provide both a repository URL and an issue number.';
            return;
        }

        runBtn.disabled = true;
        runBtn.innerHTML = '<span class="btn-icon">⏳</span><span>Running Workflow…</span>';
        runBtn.classList.add('loading');
        resetUI();
        activeRunId = null;

        try {
            const response = await fetch('/api/v1/runs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repository_url: repoUrl, issue_number: issueNumber, dry_run: dryRun })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Unable to start workflow');
            }
            activeRunId = data.run_id;
            pollRun(data.run_id);
        } catch (err) {
            formError.textContent = err.message || 'Failed to start workflow';
            runBtn.disabled = false;
            runBtn.classList.remove('loading');
            runBtn.innerHTML = '<span class="btn-icon">↗</span><span>Run Workflow</span>';
        }
    });

    function pollRun(runId) {
        if (intervalHandle) clearInterval(intervalHandle);
        intervalHandle = setInterval(async () => {
            try {
                const res = await fetch(`/api/v1/runs/${runId}`);
                const data = await res.json();
                updateFeed(data.events || []);
                if (data.state) {
                    renderPipeline(data.events || []);
                    updateResults(data.state);
                    updateProgress(data.state);
                }
                if (data.status === 'success' || data.status === 'failed') {
                    clearInterval(intervalHandle);
                    runBtn.disabled = false;
                    runBtn.classList.remove('loading');
                    runBtn.innerHTML = '<span class="btn-icon">↗</span><span>Run Workflow</span>';
                }
            } catch (error) {
                console.error(error);
            }
        }, 900);
    }

    document.addEventListener('click', (event) => {
        const target = event.target.closest('[data-agent]');
        if (target) openDrawer(target.getAttribute('data-agent'));
        if (event.target.matches('[data-close="drawer"]')) closeDrawer();
    });

    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('light');
        themeToggle.textContent = document.body.classList.contains('light') ? '☾' : '☀';
    });

    navItems.forEach((item) => item.addEventListener('click', () => {
        navItems.forEach((entry) => entry.classList.remove('active'));
        item.classList.add('active');
        pageTitle.textContent = item.textContent;
    }));

    drawer.addEventListener('click', (event) => {
        if (event.target.classList.contains('drawer-backdrop')) closeDrawer();
    });

    window.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeDrawer();
    });

    function initForm() {
        if (runForm) {
            runForm.reset();
        }
        clearFormInputs();
        window.requestAnimationFrame(clearFormInputs);
        setTimeout(clearFormInputs, 100);
        if (repoUrlInput) {
            repoUrlInput.focus();
        }
    }

    if (runForm) {
        runForm.addEventListener('reset', clearFormInputs);
    }

    resetUI();
    initForm();
    window.addEventListener('load', initForm);
    window.addEventListener('pageshow', () => {
        initForm();
        resetUI();
    });
    checkHealth();
});

function escapeHtml(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
