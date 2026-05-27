import { useEffect, useMemo, useState } from 'react'
import { marked } from 'marked'
import { apiRequest } from './api'

const sections = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'tech-stacks', label: 'Tech Stacks' },
  { key: 'knowledge', label: 'Knowledge Base' },
]

function Card({ title, children }) {
  return (
    <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function Notice({ tone = 'info', children }) {
  const styles = {
    info: 'bg-blue-50 text-blue-800',
    error: 'bg-red-50 text-red-800',
    success: 'bg-emerald-50 text-emerald-800',
  }
  return <p className={`rounded-md p-2 text-sm ${styles[tone]}`}>{children}</p>
}

export default function App() {
  const [activeSection, setActiveSection] = useState('dashboard')
  const [email, setEmail] = useState('employee@company.com')
  const [token, setToken] = useState('')
  const [status, setStatus] = useState({ tone: 'info', text: '' })
  const [isLoading, setIsLoading] = useState(false)

  const [dashboard, setDashboard] = useState(null)
  const [templates, setTemplates] = useState([])
  const [users, setUsers] = useState([])
  const [assignTemplateId, setAssignTemplateId] = useState('')
  const [assignUserId, setAssignUserId] = useState('')
  const [stackName, setStackName] = useState('Python Automation Development Stack')
  const [stackDescription, setStackDescription] = useState('Baseline skills for automation engineers.')
  const [skillRows, setSkillRows] = useState([{ skill_name: 'Python', min_proficiency_required: 4 }])
  const [gapUserId, setGapUserId] = useState('')
  const [gapResult, setGapResult] = useState(null)
  const [markdown, setMarkdown] = useState('# Welcome to Silo')

  const markdownHtml = useMemo(() => marked.parse(markdown), [markdown])
  const loggedIn = Boolean(token)

  const notify = (text, tone = 'info') => setStatus({ tone, text })

  const runAction = async (fn) => {
    setIsLoading(true)
    try {
      await fn()
    } finally {
      setIsLoading(false)
    }
  }

  const refreshLookups = async () => {
    const templateData = await apiRequest('/tech-stacks', { token })
    let userData = []
    try {
      userData = await apiRequest('/users', { token })
    } catch {
      const me = await apiRequest('/users/me', { token })
      userData = [{ id: me.id, name: me.name, email: me.email, role: me.role }]
    }
    setTemplates(templateData)
    setUsers(userData)
    if (templateData.length && !assignTemplateId) setAssignTemplateId(String(templateData[0].id))
    if (userData.length && !assignUserId) {
      setAssignUserId(String(userData[0].id))
      setGapUserId(String(userData[0].id))
    }
  }

  useEffect(() => {
    if (!token) return
    runAction(async () => {
      try {
        await refreshLookups()
      } catch (error) {
        notify(error.message, 'error')
      }
    })
  }, [token])

  const login = async () =>
    runAction(async () => {
      try {
        const data = await apiRequest('/auth/login', { method: 'POST', body: { email } })
        setToken(data.access_token)
        notify('Logged in successfully', 'success')
      } catch (error) {
        notify(error.message, 'error')
      }
    })

  const loadEmployeeDashboard = async () =>
    runAction(async () => {
      try {
        setDashboard(await apiRequest('/dashboards/employee', { token }))
        notify('Dashboard refreshed', 'success')
      } catch (error) {
        notify(error.message, 'error')
      }
    })

  const createStack = async () =>
    runAction(async () => {
      try {
        const template = await apiRequest('/tech-stacks', {
          method: 'POST',
          token,
          body: { name: stackName, description: stackDescription },
        })
        await Promise.all(
          skillRows
            .filter((row) => row.skill_name.trim())
            .map((row) =>
              apiRequest(`/tech-stacks/${template.id}/skills`, {
                method: 'POST',
                token,
                body: row,
              }),
            ),
        )
        await refreshLookups()
        setAssignTemplateId(String(template.id))
        notify(`Created stack ${template.name}`, 'success')
      } catch (error) {
        notify(error.message, 'error')
      }
    })

  const assignStack = async () =>
    runAction(async () => {
      try {
        await apiRequest(`/tech-stacks/${assignTemplateId}/assign`, {
          method: 'POST',
          token,
          body: { user_id: Number(assignUserId) },
        })
        notify('Stack assigned', 'success')
      } catch (error) {
        notify(error.message, 'error')
      }
    })

  const loadGap = async () =>
    runAction(async () => {
      try {
        setGapResult(await apiRequest(`/users/${gapUserId}/gap-analysis`, { token }))
        notify('Gap analysis loaded', 'success')
      } catch (error) {
        notify(error.message, 'error')
      }
    })

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-4 bg-slate-50 p-4 text-slate-900">
      <header className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <h1 className="text-2xl font-bold">Silo</h1>
        <p className="text-sm text-slate-600">Knowledge, skills, and tech stack readiness platform</p>
      </header>

      <Card title="Authentication">
        <div className="flex flex-col gap-2 md:flex-row">
          <input
            className="w-full rounded-md border border-slate-300 p-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            aria-label="Company email"
          />
          <button
            className="rounded-md bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
            onClick={login}
            disabled={isLoading}
          >
            {isLoading ? 'Working...' : 'Login'}
          </button>
        </div>
        <p className="mt-2 text-xs break-all text-slate-600">JWT: {token || 'Not logged in'}</p>
      </Card>

      {status.text && <Notice tone={status.tone}>{status.text}</Notice>}

      <nav className="flex flex-wrap gap-2" aria-label="Primary">
        {sections.map((section) => (
          <button
            key={section.key}
            className={`rounded-md px-3 py-2 text-sm ${
              activeSection === section.key ? 'bg-slate-900 text-white' : 'bg-white text-slate-700 ring-1 ring-slate-200'
            }`}
            onClick={() => setActiveSection(section.key)}
          >
            {section.label}
          </button>
        ))}
      </nav>

      {!loggedIn && <Notice>Login first to access dashboards and management features.</Notice>}

      {activeSection === 'dashboard' && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Employee Dashboard">
            <button
              className="rounded-md bg-emerald-700 px-3 py-2 text-white disabled:opacity-50"
              onClick={loadEmployeeDashboard}
              disabled={!loggedIn || isLoading}
            >
              Refresh Dashboard
            </button>
            {!dashboard && <p className="mt-2 text-sm text-slate-500">No dashboard data loaded yet.</p>}
            {dashboard && (
              <div className="mt-3 space-y-2 text-sm">
                <p className="font-medium">Progress: {dashboard.progress_percent}%</p>
                <p>Up next sessions: {dashboard.up_next_schedules.length}</p>
                <p>In progress tasks: {dashboard.in_progress_tasks.length}</p>
              </div>
            )}
          </Card>

          <Card title='My Target Requirements'>
            <div className="flex flex-col gap-2 md:flex-row">
              <select
                className="w-full rounded-md border border-slate-300 p-2"
                value={gapUserId}
                onChange={(e) => setGapUserId(e.target.value)}
                disabled={!users.length}
              >
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name} ({user.role})
                  </option>
                ))}
              </select>
              <button
                className="rounded-md bg-indigo-700 px-3 py-2 text-white disabled:opacity-50"
                onClick={loadGap}
                disabled={!loggedIn || !gapUserId || isLoading}
              >
                Load
              </button>
            </div>
            {!gapResult && <p className="mt-2 text-sm text-slate-500">No gap analysis loaded yet.</p>}
            {gapResult?.analysis?.map((template) => (
              <div key={template.template_id} className="mt-3 rounded-md border border-slate-200 p-3 text-sm">
                <p className="font-semibold">{template.template_name}</p>
                {template.below_requirement.map((item) => (
                  <p key={`b-${item.skill_name}`} className="text-amber-700">
                    {item.skill_name}: Level {item.actual_level}/{item.required_level} (-{item.gap})
                  </p>
                ))}
                {template.meets_requirement.map((item) => (
                  <p key={`m-${item.skill_name}`} className="text-emerald-700">
                    ✓ {item.skill_name}: Level {item.actual_level}/{item.required_level}
                  </p>
                ))}
                {template.missing_skills.map((item) => (
                  <p key={`x-${item.skill_name}`} className="text-red-700">
                    Missing: {item.skill_name} (Need {item.required_level})
                  </p>
                ))}
              </div>
            ))}
          </Card>
        </div>
      )}

      {activeSection === 'tech-stacks' && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Stack Designer">
            <div className="space-y-2">
              <input
                className="w-full rounded-md border border-slate-300 p-2"
                value={stackName}
                onChange={(e) => setStackName(e.target.value)}
                placeholder="Stack name"
              />
              <textarea
                className="w-full rounded-md border border-slate-300 p-2"
                value={stackDescription}
                onChange={(e) => setStackDescription(e.target.value)}
                placeholder="Stack description"
              />
              {skillRows.map((row, idx) => (
                <div key={idx} className="grid grid-cols-2 gap-2">
                  <input
                    className="rounded-md border border-slate-300 p-2"
                    value={row.skill_name}
                    onChange={(e) => {
                      const next = [...skillRows]
                      next[idx].skill_name = e.target.value
                      setSkillRows(next)
                    }}
                    placeholder="Skill"
                  />
                  <select
                    className="rounded-md border border-slate-300 p-2"
                    value={row.min_proficiency_required}
                    onChange={(e) => {
                      const next = [...skillRows]
                      next[idx].min_proficiency_required = Number(e.target.value)
                      setSkillRows(next)
                    }}
                  >
                    {[1, 2, 3, 4, 5].map((level) => (
                      <option key={level} value={level}>
                        Level {level}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
              <div className="flex gap-2">
                <button
                  className="rounded-md border border-slate-300 px-3 py-1"
                  onClick={() => setSkillRows([...skillRows, { skill_name: '', min_proficiency_required: 1 }])}
                >
                  Add Skill
                </button>
                <button
                  className="rounded-md bg-slate-900 px-3 py-1 text-white disabled:opacity-50"
                  onClick={createStack}
                  disabled={!loggedIn || isLoading}
                >
                  Create Stack
                </button>
              </div>
            </div>
          </Card>

          <Card title="Assign Tech Stack">
            <div className="grid gap-2">
              <select
                className="rounded-md border border-slate-300 p-2"
                value={assignTemplateId}
                onChange={(e) => setAssignTemplateId(e.target.value)}
                disabled={!templates.length}
              >
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
              <select
                className="rounded-md border border-slate-300 p-2"
                value={assignUserId}
                onChange={(e) => setAssignUserId(e.target.value)}
                disabled={!users.length}
              >
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name} ({user.role})
                  </option>
                ))}
              </select>
            </div>
            <button
              className="mt-2 rounded-md bg-slate-900 px-3 py-2 text-white disabled:opacity-50"
              onClick={assignStack}
              disabled={!loggedIn || !assignTemplateId || !assignUserId || isLoading}
            >
              Assign Stack
            </button>
          </Card>
        </div>
      )}

      {activeSection === 'knowledge' && (
        <Card title="Documentation Editor + Preview">
          <textarea
            className="h-48 w-full rounded-md border border-slate-300 p-2"
            value={markdown}
            onChange={(e) => setMarkdown(e.target.value)}
          />
          <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="mb-2 text-xs uppercase tracking-wide text-slate-600">Rendered Markdown</p>
            <article className="prose max-w-none" dangerouslySetInnerHTML={{ __html: markdownHtml }} />
          </div>
        </Card>
      )}
    </main>
  )
}
