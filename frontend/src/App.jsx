import { useMemo, useState } from 'react'
import { marked } from 'marked'

const API_BASE = 'http://localhost:8000/api'

async function api(path, method = 'GET', token, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `****** } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed: ${res.status}`)
  }
  return res.headers.get('content-type')?.includes('application/json') ? res.json() : res.text()
}

function Card({ title, children }) {
  return (
    <section className="rounded-lg bg-white p-4 shadow">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}

export default function App() {
  const [email, setEmail] = useState('employee@company.com')
  const [token, setToken] = useState('')
  const [message, setMessage] = useState('')
  const [markdown, setMarkdown] = useState('# Welcome to Silo')
  const [stackName, setStackName] = useState('Python Automation Development Stack')
  const [stackDescription, setStackDescription] = useState('Baseline skills for automation engineers.')
  const [skillRows, setSkillRows] = useState([{ skill_name: 'Python', min_proficiency_required: 4 }])
  const [assignTemplateId, setAssignTemplateId] = useState('1')
  const [assignUserId, setAssignUserId] = useState('1')
  const [gapUserId, setGapUserId] = useState('1')
  const [gapResult, setGapResult] = useState(null)
  const [dashboard, setDashboard] = useState(null)

  const markdownHtml = useMemo(() => marked.parse(markdown), [markdown])

  const login = async () => {
    try {
      const data = await api('/auth/login', 'POST', null, { email })
      setToken(data.access_token)
      setMessage('Logged in successfully')
    } catch (e) {
      setMessage(e.message)
    }
  }

  const loadEmployeeDashboard = async () => {
    try {
      setDashboard(await api('/dashboards/employee', 'GET', token))
    } catch (e) {
      setMessage(e.message)
    }
  }

  const createStack = async () => {
    try {
      const template = await api('/tech-stacks', 'POST', token, {
        name: stackName,
        description: stackDescription,
      })
      for (const row of skillRows) {
        await api(`/tech-stacks/${template.id}/skills`, 'POST', token, row)
      }
      setAssignTemplateId(String(template.id))
      setMessage(`Created stack ${template.name}`)
    } catch (e) {
      setMessage(e.message)
    }
  }

  const assignStack = async () => {
    try {
      await api(`/tech-stacks/${assignTemplateId}/assign`, 'POST', token, {
        user_id: Number(assignUserId),
      })
      setMessage('Stack assigned')
    } catch (e) {
      setMessage(e.message)
    }
  }

  const loadGap = async () => {
    try {
      setGapResult(await api(`/users/${gapUserId}/gap-analysis`, 'GET', token))
    } catch (e) {
      setMessage(e.message)
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-4 p-4">
      <h1 className="text-2xl font-bold">Silo: Onboarding, Training, and Knowledge</h1>
      {message && <p className="rounded bg-blue-50 p-2 text-sm text-blue-800">{message}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Authentication">
          <div className="flex gap-2">
            <input
              className="w-full rounded border p-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
            <button className="rounded bg-slate-800 px-3 py-2 text-white" onClick={login}>
              Login
            </button>
          </div>
          <p className="mt-2 text-xs break-all">JWT: {token || 'Not logged in'}</p>
        </Card>

        <Card title="Employee Dashboard">
          <button className="rounded bg-emerald-700 px-3 py-2 text-white" onClick={loadEmployeeDashboard}>
            Refresh Dashboard
          </button>
          {dashboard && (
            <div className="mt-3 space-y-2 text-sm">
              <p className="font-medium">Progress Ring Value: {dashboard.progress_percent}%</p>
              <p>Up Next Sessions: {dashboard.up_next_schedules.length}</p>
              <p>In Progress Tasks: {dashboard.in_progress_tasks.length}</p>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Manager Portal - Stack Designer">
          <div className="space-y-2">
            <input className="w-full rounded border p-2" value={stackName} onChange={(e) => setStackName(e.target.value)} />
            <textarea
              className="w-full rounded border p-2"
              value={stackDescription}
              onChange={(e) => setStackDescription(e.target.value)}
            />
            {skillRows.map((row, idx) => (
              <div key={idx} className="grid grid-cols-2 gap-2">
                <input
                  className="rounded border p-2"
                  value={row.skill_name}
                  onChange={(e) => {
                    const copy = [...skillRows]
                    copy[idx].skill_name = e.target.value
                    setSkillRows(copy)
                  }}
                />
                <select
                  className="rounded border p-2"
                  value={row.min_proficiency_required}
                  onChange={(e) => {
                    const copy = [...skillRows]
                    copy[idx].min_proficiency_required = Number(e.target.value)
                    setSkillRows(copy)
                  }}
                >
                  {[1, 2, 3, 4, 5].map((lvl) => (
                    <option key={lvl} value={lvl}>
                      Level {lvl}
                    </option>
                  ))}
                </select>
              </div>
            ))}
            <div className="flex gap-2">
              <button
                className="rounded border px-3 py-1"
                onClick={() => setSkillRows([...skillRows, { skill_name: '', min_proficiency_required: 1 }])}
              >
                Add Skill Row
              </button>
              <button className="rounded bg-slate-800 px-3 py-1 text-white" onClick={createStack}>
                Create New Stack
              </button>
            </div>
          </div>
        </Card>

        <Card title="Manager Portal - Assignment Dropdown">
          <div className="grid grid-cols-2 gap-2">
            <input
              className="rounded border p-2"
              value={assignTemplateId}
              onChange={(e) => setAssignTemplateId(e.target.value)}
              placeholder="Template ID"
            />
            <input
              className="rounded border p-2"
              value={assignUserId}
              onChange={(e) => setAssignUserId(e.target.value)}
              placeholder="Employee User ID"
            />
          </div>
          <button className="mt-2 rounded bg-slate-800 px-3 py-2 text-white" onClick={assignStack}>
            Assign Tech Stack
          </button>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Documentation Wiki Editor + Viewer">
          <textarea
            className="h-48 w-full rounded border p-2"
            value={markdown}
            onChange={(e) => setMarkdown(e.target.value)}
          />
          <div className="mt-3 rounded border bg-slate-50 p-3">
            <p className="mb-2 text-xs uppercase text-slate-600">Rendered Markdown</p>
            <article className="prose" dangerouslySetInnerHTML={{ __html: markdownHtml }} />
          </div>
        </Card>

        <Card title='Employee Portal - "My Target Requirements" Widget'>
          <div className="flex gap-2">
            <input
              className="w-full rounded border p-2"
              value={gapUserId}
              onChange={(e) => setGapUserId(e.target.value)}
              placeholder="User ID"
            />
            <button className="rounded bg-indigo-700 px-3 py-2 text-white" onClick={loadGap}>
              Load
            </button>
          </div>
          {gapResult?.analysis?.map((template) => (
            <div key={template.template_id} className="mt-3 rounded border p-3 text-sm">
              <p className="font-semibold">{template.template_name}</p>
              {template.below_requirement.map((item) => (
                <p key={`b-${item.skill_name}`} className="text-amber-700">
                  {item.skill_name}: Level {item.actual_level} / {item.required_level} Required (-{item.gap} Levels)
                </p>
              ))}
              {template.meets_requirement.map((item) => (
                <p key={`m-${item.skill_name}`} className="text-emerald-700">
                  ✓ {item.skill_name}: Level {item.actual_level} / {item.required_level} Required
                </p>
              ))}
              {template.missing_skills.map((item) => (
                <p key={`x-${item.skill_name}`} className="text-red-700">
                  Missing: {item.skill_name} (Requires Level {item.required_level})
                </p>
              ))}
            </div>
          ))}
        </Card>
      </div>
    </main>
  )
}
