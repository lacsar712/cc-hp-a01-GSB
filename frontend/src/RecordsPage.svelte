<script>
  import { onMount } from 'svelte'
  import { api, auxStatus } from './api.js'

  export let role

  let rows = []
  let auxRows = []
  let herb = '白芍'
  let tempC = 110
  let minutes = 10
  let auxId = ''
  let error = ''
  let notice = ''
  let openId = null

  async function load() {
    ;[rows, auxRows] = await Promise.all([api('/api/batches'), api('/api/aux-batches')])
  }

  async function save() {
    error = ''
    notice = ''
    try {
      const body = {
        herb,
        steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
      }
      if (auxId !== '') body.aux_batch_id = Number(auxId)
      await api('/api/batches', { method: 'POST', body: JSON.stringify(body) })
      notice = '文书已写入，批号正文随文书冻结'
      await load()
    } catch (err) {
      error = err.message
    }
  }

  function toggle(id) {
    openId = openId === id ? null : id
  }

  onMount(load)
</script>

<main class="page">
  {#if role === 'writer'}
    <section class="card">
      <h2>写清炒文书</h2>
      <div class="form-row">
        <label>饮片 <input bind:value={herb} placeholder="饮片" /></label>
        <label>温度(℃) <input type="number" bind:value={tempC} /></label>
        <label>时长(分) <input type="number" bind:value={minutes} /></label>
        <label>
          辅料批号
          <select bind:value={auxId}>
            <option value="">— 从批号册点选 —</option>
            {#each auxRows as a}
              <option value={a.id}>
                {a.material} · {a.lot_no} · 失效日 {a.expires_on}{auxStatus(a) === 'expired' ? '（已失效）' : ''}
              </option>
            {/each}
          </select>
        </label>
        <button class="primary" on:click={save}>写入清炒记录</button>
      </div>
      {#if auxRows.length === 0}
        <p class="warn">批号册为空，请先到顶栏「辅料批号册」登记辅料批号，再开炒。</p>
      {/if}
      {#if error}<p class="err">{error}</p>{/if}
      {#if notice}<p class="ok">{notice}</p>{/if}
    </section>
  {/if}

  <section class="card">
    <h2>炮制文书</h2>
    {#if rows.length === 0}
      <p class="muted">暂无记录</p>
    {/if}
    <ul class="records">
      {#each rows as row}
        <li>
          <button class="row-head" on:click={() => toggle(row.id)}>
            <span class="herb">{row.herb}</span>
            <span class="verdict" class:pass={row.verdict === '放行'}>{row.verdict}</span>
            <span class="reason">{row.reason}</span>
            <span class="mini">
              {#if row.doc.aux_batch}
                批号 {row.doc.aux_batch.lot_no}
              {:else}
                旧记录未挂批号
              {/if}
            </span>
            <span class="caret">{openId === row.id ? '▲' : '▼'}</span>
          </button>
          {#if openId === row.id}
            <div class="detail">
              {#if row.doc.aux_batch}
                <p class="frozen">
                  批号正文（已冻结）：辅料 {row.doc.aux_batch.material} · 批号 {row.doc.aux_batch.lot_no} · 失效日 {row.doc.aux_batch.expires_on}
                </p>
              {:else}
                <p class="frozen">未挂辅料批号（批号册启用前的旧记录）</p>
              {/if}
              <ul class="steps">
                {#each row.doc.steps as s}
                  <li>{s.name} · {s.temp_c}℃ · {s.minutes} 分钟</li>
                {/each}
              </ul>
              <p class="muted">记录人 {row.created_by}</p>
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
</main>

<style>
  .page {
    max-width: 860px;
    margin: 20px auto;
    padding: 0 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .card {
    background: #fff;
    border: 1px solid #e8ddcf;
    border-radius: 10px;
    padding: 16px 20px;
  }
  h2 {
    margin: 0 0 12px;
    font-size: 16px;
    color: #7c2d12;
  }
  .form-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: flex-end;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 13px;
    color: #6b5a48;
  }
  input,
  select {
    padding: 6px 8px;
    border: 1px solid #d8c9b8;
    border-radius: 6px;
    font-size: 14px;
  }
  .primary {
    background: #7c2d12;
    color: #fff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
  }
  .warn {
    color: #b45309;
  }
  .err {
    color: #b91c1c;
  }
  .ok {
    color: #15803d;
  }
  .muted {
    color: #8a7a68;
    font-size: 13px;
  }
  .records {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .records > li {
    border-top: 1px solid #f0e7da;
  }
  .row-head {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    background: none;
    border: none;
    padding: 10px 4px;
    cursor: pointer;
    font-size: 14px;
    color: inherit;
    text-align: left;
  }
  .herb {
    font-weight: 600;
    min-width: 56px;
  }
  .verdict {
    color: #b91c1c;
    font-weight: 600;
  }
  .verdict.pass {
    color: #15803d;
  }
  .reason {
    color: #6b5a48;
    flex: 1;
  }
  .mini {
    color: #8a7a68;
    font-size: 12px;
  }
  .caret {
    color: #8a7a68;
  }
  .detail {
    padding: 4px 4px 12px;
  }
  .frozen {
    background: #fdf3e7;
    border: 1px solid #edd9bd;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 13px;
  }
  .steps {
    margin: 8px 0;
    padding-left: 20px;
    font-size: 13px;
  }
</style>
