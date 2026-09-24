<script>
  function toISODate(d) {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }
  function datePlus(days) {
    const d = new Date()
    d.setDate(d.getDate() + days)
    return toISODate(d)
  }
  function daysLeft(iso) {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const d = new Date(iso + 'T00:00:00')
    return Math.round((d - today) / 86400000)
  }

  let username = $state('processor')
  let password = $state('herb123456')
  let token = $state(localStorage.getItem('herb_token') || '')
  let role = $state(localStorage.getItem('herb_role') || '')
  let view = $state('ledger')

  let lots = $state([])
  let rows = $state([])
  let openDocs = $state({})

  // 批号册登记表单
  let regName = $state('蜜')
  let regLot = $state('批甲')
  let regExpires = $state(datePlus(2))
  let regError = $state('')

  // 开炒表单：批号必须点选，默认空
  let herb = $state('白芍')
  let tempC = $state(110)
  let minutes = $state(10)
  let selectedLot = $state('')
  let error = $state('')

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || '请求失败')
    return data
  }

  async function enter() {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    token = data.access_token
    role = data.role
    localStorage.setItem('herb_token', token)
    localStorage.setItem('herb_role', role)
    view = 'ledger'
    await loadAll()
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
  }

  async function loadLots() {
    lots = await api('/api/excipient-lots')
  }

  async function loadRows() {
    rows = await api('/api/batches')
  }

  async function loadAll() {
    await Promise.all([loadLots(), loadRows()])
  }

  async function registerLot() {
    regError = ''
    try {
      await api('/api/excipient-lots', {
        method: 'POST',
        body: JSON.stringify({ name: regName, lot_no: regLot, expires_on: regExpires }),
      })
      await loadLots()
    } catch (err) {
      regError = err.message
    }
  }

  async function changeExpiry(lot, ev) {
    const next = ev.target.value
    if (!next || next === lot.expires_on) return
    lot.editError = ''
    try {
      await api(`/api/excipient-lots/${lot.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ expires_on: next }),
      })
      await loadLots()
    } catch (err) {
      lot.editError = err.message
    }
  }

  async function save() {
    error = ''
    const lot = lots.find((l) => String(l.id) === String(selectedLot))
    // 缺选或选到已过失效日，一律拒写并说明原因
    if (!selectedLot || !lot) {
      error = '缺选辅料批号：请从批号册中点选未失效批号'
      return
    }
    if (lot.expired) {
      error = `辅料批号已过期：${lot.name} ${lot.lot_no} 失效日 ${lot.expires_on}`
      return
    }
    try {
      await api('/api/batches', {
        method: 'POST',
        body: JSON.stringify({
          herb,
          steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
          excipient_id: Number(selectedLot),
        }),
      })
      selectedLot = ''
      await loadRows()
    } catch (err) {
      error = err.message
    }
  }

  const expiredLots = $derived(lots.filter((l) => l.expired))
  const soonLots = $derived(lots.filter((l) => !l.expired && daysLeft(l.expires_on) <= 7))

  if (token) loadAll()
</script>

<main class:fullscreen={view === 'ledger' && token}>
  {#if !token}
    <h1>饮片炮制记录台</h1>
    <p>先建辅料批号册，再允许开炒。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。</p>
    <input bind:value={username} />
    <input type="password" bind:value={password} />
    <button onclick={enter}>登录</button>
    <p>processor / herb123456 可登册、可开炒；checker / check123456 只能翻册与冻结正文</p>
  {:else}
    <header class="topbar">
      <h1>饮片炮制记录台</h1>
      <nav>
        <button class:active={view === 'ledger'} onclick={() => (view = 'ledger')}>批号册</button>
        <button class:active={view === 'fry'} onclick={() => (view = 'fry')}>开炒炮制</button>
      </nav>
      <div class="who">
        <span class="role">{role === 'writer' ? '炮制员' : '质检员'}（只读不可登册/开炒时按钮隐藏）</span>
        <button onclick={leave}>退出</button>
      </div>
    </header>

    {#if view === 'ledger'}
      <!-- 批号册：独占整屏的落地页 -->
      <section class="ledger">
        <h2>辅料批号册</h2>

        <div class="reminders">
          {#if expiredLots.length === 0 && soonLots.length === 0}
            <p class="ok">暂无失效或临近失效批号。</p>
          {/if}
          {#if expiredLots.length > 0}
            <p class="alert danger">已过失效日（开炒禁用）：
              {#each expiredLots as l}{l.name}·{l.lot_no}（{l.expires_on}） {/each}
            </p>
          {/if}
          {#if soonLots.length > 0}
            <p class="alert warn">7 日内将失效：
              {#each soonLots as l}{l.name}·{l.lot_no}（剩 {daysLeft(l.expires_on)} 天） {/each}
            </p>
          {/if}
        </div>

        {#if role === 'writer'}
          <form class="register" onsubmit={(e) => { e.preventDefault(); registerLot() }}>
            <h3>登记新批号</h3>
            <input bind:value={regName} placeholder="辅料名（如 蜜）" />
            <input bind:value={regLot} placeholder="批号串（如 批甲）" />
            <label>失效日 <input type="date" bind:value={regExpires} /></label>
            <button type="submit">登册</button>
            {#if regError}<p class="alert danger">{regError}</p>{/if}
          </form>
        {:else}
          <p class="readonly-hint">质检员只读：可查阅批号册，不能登册。</p>
        {/if}

        <table class="lot-table">
          <thead>
            <tr>
              <th>辅料名</th><th>批号串</th><th>失效日</th><th>状态</th><th>登记者</th>
              {#if role === 'writer'}<th>改正失效日</th>{/if}
            </tr>
          </thead>
          <tbody>
            {#each lots as lot (lot.id)}
              <tr class:expired={lot.expired}>
                <td>{lot.name}</td>
                <td>{lot.lot_no}</td>
                <td>{lot.expires_on}</td>
                <td>
                  {#if lot.expired}
                    <span class="tag expired">已过期</span>
                  {:else}
                    <span class="tag valid">未失效（剩 {daysLeft(lot.expires_on)} 天）</span>
                  {/if}
                </td>
                <td>{lot.registered_by}</td>
                {#if role === 'writer'}
                  <td>
                    <input type="date" value={lot.expires_on} onchange={(e) => changeExpiry(lot, e)} />
                    {#if lot.editError}<p class="alert danger">{lot.editError}</p>{/if}
                    <p class="note">仅改册；已冻结文书正文不随之改写</p>
                  </td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {:else}
      <section class="fry">
        <h2>清炒文书</h2>
        {#if role === 'writer'}
          <form onsubmit={(e) => { e.preventDefault(); save() }}>
            <input bind:value={herb} placeholder="饮片（如 白芍）" />
            <input type="number" bind:value={tempC} placeholder="温度℃" />
            <input type="number" bind:value={minutes} placeholder="时长(分)" />
            <select bind:value={selectedLot}>
              <option value="">— 请从批号册点选未失效批号 —</option>
              {#each lots as lot (lot.id)}
                <option value={lot.id} disabled={lot.expired}>
                  {lot.name} · {lot.lot_no} · 失效日 {lot.expires_on}{lot.expired ? '（已过期）' : ''}
                </option>
              {/each}
            </select>
            <button type="submit">写入清炒记录</button>
          </form>
          {#if error}<p class="alert danger">{error}</p>{/if}
        {:else}
          <p class="readonly-hint">质检员只读：可展开查阅已冻结正文，不能开炒。</p>
        {/if}

        <h3>已冻结文书</h3>
        <ul class="records">
          {#each rows as row}
            <li>
              <button class="link" onclick={() => (openDocs[row.id] = !openDocs[row.id])}>
                {openDocs[row.id] ? '收起' : '打开'} #{row.id} {row.herb} · {row.verdict} · {row.reason}
              </button>
              {#if openDocs[row.id]}
                <div class="frozen-doc">
                  <p>冻结正文（开炒当时随文书定格，事后改册不回写）：</p>
                  {#if row.doc.excipient}
                    <ul>
                      <li>辅料名：{row.doc.excipient.name}</li>
                      <li>批号串：{row.doc.excipient.lot_no}</li>
                      <li>失效日：{row.doc.excipient.expires_on}</li>
                    </ul>
                  {:else}
                    <p>（该笔为旧样例，无辅料批号）</p>
                  {/if}
                  <ul>
                    {#each row.doc.steps ?? [] as s}
                      <li>{s.name}：温度 {s.temp_c}℃，时长 {s.minutes} 分钟</li>
                    {/each}
                  </ul>
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</main>

<style>
  :global(body) { margin: 0; }
  main {
    font-family: sans-serif;
    max-width: 960px;
    margin: 0 auto;
    padding: 24px;
    color: #3f2f1f;
    box-sizing: border-box;
  }
  main.fullscreen {
    max-width: none;
    min-height: 100vh;
    padding: 0 32px 32px;
  }
  h1 { color: #7c2d12; font-size: 20px; margin: 0; }
  h2 { color: #7c2d12; }

  .topbar {
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 14px 0;
    border-bottom: 2px solid #7c2d12;
    flex-wrap: wrap;
  }
  .topbar nav { display: flex; gap: 8px; }
  .topbar nav button {
    padding: 8px 16px;
    border: 1px solid #7c2d12;
    background: #fff;
    color: #7c2d12;
    cursor: pointer;
    border-radius: 4px;
  }
  .topbar nav button.active { background: #7c2d12; color: #fff; }
  .who { margin-left: auto; display: flex; align-items: center; gap: 12px; }
  .role { color: #8a6a50; font-size: 13px; }

  .ledger { padding-top: 20px; }
  .lot-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  .lot-table th, .lot-table td {
    border: 1px solid #d8c4ad;
    padding: 8px 10px;
    text-align: left;
  }
  .lot-table thead { background: #f6ece1; }
  tr.expired { background: #fdeceb; }
  .tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; }
  .tag.valid { background: #e3f2e3; color: #1b5e20; }
  .tag.expired { background: #f8d7da; color: #8a1f1f; }

  .alert { padding: 8px 12px; border-radius: 4px; }
  .alert.danger { background: #f8d7da; color: #8a1f1f; }
  .alert.warn { background: #fff3cd; color: #7a5b00; }
  .ok { color: #1b5e20; }
  .note { color: #9a8266; font-size: 12px; margin: 4px 0 0; }

  .register {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    background: #fbf5ee;
    border: 1px solid #e3d3c0;
    padding: 12px;
    border-radius: 6px;
  }
  .register h3 { width: 100%; margin: 0; }
  .readonly-hint { color: #8a6a50; font-style: italic; }

  input, select { margin-right: 8px; padding: 6px; }
  button { cursor: pointer; }
  form { margin: 12px 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

  .records { list-style: none; padding: 0; }
  .records > li { border-bottom: 1px solid #e3d3c0; padding: 8px 0; }
  button.link {
    background: none;
    border: none;
    color: #7c2d12;
    text-decoration: underline;
    padding: 0;
  }
  .frozen-doc {
    margin-top: 8px;
    padding: 10px 14px;
    background: #fbf5ee;
    border-left: 3px solid #7c2d12;
    border-radius: 0 4px 4px 0;
  }
</style>
