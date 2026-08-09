document.addEventListener('DOMContentLoaded', () => {
  const byId = (id) => document.getElementById(id);
  const form = byId('runForm');
  const agentOrder = [
    'issue_loader', 'code_reader', 'planner', 'research_agent', 'code_writer',
    'test_writer', 'test_runner', 'reviewer', 'pr_opener'
  ];

  form.addEventListener('submit', () => {
    byId('details').hidden = true;
    ['issueContent', 'planContent', 'diffContent', 'testContent', 'reviewContent', 'prContent']
      .forEach((id) => { byId(id).textContent = ''; });
    byId('agentOutput').textContent = 'Starting a fresh repository workflow...';
  }, {capture: true});

  function setCardState(card, state, detail) {
    card.classList.remove('success', 'running', 'pending', 'skipped', 'failed');
    card.classList.add(state);
    const badge = card.querySelector('.agent-status');
    const description = card.querySelector('p');
    const footer = card.querySelector('.agent-time');
    if (badge) badge.textContent = state === 'failed' ? 'FAILED' : state.toUpperCase();
    if (description) description.textContent = detail;
    if (footer) footer.textContent = state === 'success' ? 'Complete' : '...';
  }

  function enforceFailedState(run) {
    const errors = run.state.errors || [];
    const message = errors.join('\n');
    const log = run.state.execution_log || [];
    const failedLog = log.find((entry) => entry.includes(': failed')) || '';
    const failedAgent = failedLog.split(':', 1)[0];
    const failedIndex = Math.max(0, agentOrder.indexOf(failedAgent));

    agentOrder.forEach((key, index) => {
      const card = document.querySelector(`[data-agent="${key}"]`);
      if (!card) return;
      if (index < failedIndex) setCardState(card, 'success', 'Completed before the failure');
      else if (index === failedIndex) setCardState(card, 'failed', errors[0] || 'Agent failed');
      else setCardState(card, 'pending', 'Not started because the workflow stopped');
    });

    const completed = failedIndex;
    const percent = Math.round((completed / agentOrder.length) * 100);
    byId('progressBar').style.width = `${percent}%`;
    byId('progressValueSmall').textContent = `${percent}%`;
    byId('progressValue').textContent = `${completed}/${agentOrder.length} agents completed`;
    byId('currentStage').textContent = `${failedAgent.replaceAll('_', ' ')} failed`;
    byId('activityDescription').textContent = errors[0] || 'The workflow stopped.';
    byId('formError').textContent = message;
    byId('agentOutput').textContent = `WORKFLOW FAILED\n\n${message}`;

    byId('details').hidden = false;
    byId('issueContent').innerHTML = '<b>Workflow stopped</b>';
    byId('planContent').textContent = message;
    byId('diffContent').textContent = 'No patch was generated.';
    byId('testContent').textContent = 'Tests were not executed.';
    byId('reviewContent').textContent = 'Review was not executed.';
    byId('prContent').textContent = 'No pull request was prepared.';
  }

  setInterval(async () => {
    const runId = byId('summaryRunId').textContent.trim();
    if (!runId || runId === '-' || runId === '—') return;
    try {
      const response = await fetch(`/api/v1/runs/${runId}`);
      if (!response.ok) return;
      const run = await response.json();
      if (run.status === 'failed' && run.state?.errors?.length) enforceFailedState(run);
    } catch (_) {
      // The main dashboard poller handles transient network errors.
    }
  }, 1000);
});
