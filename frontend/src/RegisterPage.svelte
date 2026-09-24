<script>
  import { onMount } from 'svelte'
  import { api, auxStatus, offsetDateStr } from './api.js'

  export let role

  let rows = []
  let material = '蜂蜜'
  let lotNo = '蜜炙批甲'
  let expiresOn = offsetDateStr(2)
  let error = ''
  let notice = ''
  let editId = null
  let editDate = ''

  $: expiredRows = rows.filter((r) => auxStatus(r) === 'expired')
  $: soonRows = rows.filter((r) => auxStatus(r) === 'soon')

  async function load() {
    rows = await api('/api/aux-batches')
  }

  async function register() {
    error = ''
    notice = ''
    try {
      await api('/api/aux-batches', {
        method: 'POST',
        body: JSON.stringify({ material, lot_no: lotNo, expires_on: expiresOn }),
      })
      notice = `已登记：${material} · ${lotNo} · 失效日 ${expiresOn}`
      await load()
    } catch (err) {
      error = err.message
    }
  }

  function startEdit(row) {
    editId = row.id
    editDate = row.expires_on
    error = ''
    notice = ''
  }

  async function saveEdit() {
    error = ''
    notice = ''
    try {
      await api(`/api/aux-batches/${editId}`, {
        method: 'PATCH',
        body: JSON.stringify({ expires_on: editDate }),
      })
      notice = '册上失效日已改正；已冻结的文书正文不受影响'
      editId = null
      await load()
    } catch (err) {
      error = err.message
    }
  }

  onMount(load)
</script>

<main class="register-page">
  <h1>辅料批号册</h1>

  {#if expiredRows.length > 0 || soonRows.length > 0}
    <section class="alerts">
      {#if expiredRows.length > 0}
        <p class="alert expired">
          已失效 {expiredRows.length} 条：
          {expiredRows.map((r) => `${r.material} · ${r.lot_no}（失效日 ${r.expires_on}）`).join('；')}
          —— 不得用于开炒
        </p>
      {/if}
      {#if soonRows.length > 0}
        <p class="alert soon">
          3 日内到期 {soonRows.length} 条：
          {soonRows.map((r) => `${r.material} · ${r.lot_no}（失效日 ${r.expires_on}）`).join('；')}
        </p>
      {/if}
    </section>
  {:else}
    <p class="alert none">暂无失效提醒</p>
  {/if}

  {#if role === 'writer'}
    <section class="card">
      <h2>登记辅料批号</h2>
      <div class="form-row">
        <label>辅料名 <input bind:value={material} placeholder="如：蜂蜜" /></label>
        <label>批号串 <input bind:value={lotNo} placeholder="如：蜜炙批甲" /></label>
        <label>失效日 <input type="date" bind:value={expiresOn} /></label>
        <button class="primary" on:click={register}>登记入册</button>
      </div>
      {#if error}<p class="err">{error}</p>{/if}
      {#if notice}<p class="ok">{notice}</p>{/if}
    </section>
  {:else}
    <p class="muted">质检员只读：可翻阅批号册与已冻结文书，不能登册、不能开炒。</p>
  {/if}

  <table class="sheet">
    <thead>
      <tr>
        <th>辅料名</th>
        <th>批号串</th>
        <th>失效日</th>
        <th>状态</th>
        <th>登记人</th>
        {#if role === 'writer'}<th>操作</th>{/if}
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr class={auxStatus(row)}>
          <td>{row.material}</td>
          <td>{row.lot_no}</td>
          <td>
            {#if editId === row.id}
              <input type="date" bind:value={editDate} />
            {:else}
              {row.expires_on}
            {/if}
          </td>
          <td>
            {#if auxStatus(row) === 'expired'}
              <span class="badge expired">已失效</span>
            {:else if auxStatus(row) === 'soon'}
              <span class="badge soon">临近失效</span>
            {:else}
              <span class="badge ok">有效</span>
            {/if}
          </td>
          <td>{row.created_by}</td>
          {#if role === 'writer'}
            <td>
              {#if editId === row.id}
                <button class="link" on:click={saveEdit}>保存</button>
                <button class="link" on:click={() => (editId = null)}>取消</button>
              {:else}
                <button class="link" on:click={() => startEdit(row)}>改正失效日</button>
              {/if}
            </td>
          {/if}
        </tr>
      {:else}
        <tr><td colspan="6" class="empty">册中暂无批号{role === 'writer' ? '，请先登记再开炒' : ''}</td></tr>
      {/each}
    </tbody>
  </table>
</main>

<style>
  .register-page {
    min-height: calc(100vh - 52px);
    padding: 20px 28px 40px;
    box-sizing: border-box;
  }
  h1 {
    color: #7c2d12;
    font-size: 22px;
    margin: 0 0 16px;
  }
  .alerts {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }
  .alert {
    margin: 0;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 14px;
  }
  .alert.expired {
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #b91c1c;
  }
  .alert.soon {
    background: #fffbeb;
    border: 1px solid #fde68a;
    color: #b45309;
  }
  .alert.none {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    color: #15803d;
  }
  .card {
    background: #fff;
    border: 1px solid #e8ddcf;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 16px;
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
  input {
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
  .sheet {
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    border: 1px solid #e8ddcf;
    border-radius: 10px;
    overflow: hidden;
  }
  .sheet th,
  .sheet td {
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid #f0e7da;
    font-size: 14px;
  }
  .sheet th {
    background: #f7efe4;
    color: #7c2d12;
  }
  tr.expired td {
    background: #fef2f2;
  }
  tr.soon td {
    background: #fffbeb;
  }
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge.expired {
    background: #fee2e2;
    color: #b91c1c;
  }
  .badge.soon {
    background: #fef3c7;
    color: #b45309;
  }
  .badge.ok {
    background: #dcfce7;
    color: #15803d;
  }
  .link {
    background: none;
    border: none;
    color: #7c2d12;
    cursor: pointer;
    font-size: 13px;
    text-decoration: underline;
    padding: 0 4px;
  }
  .empty {
    text-align: center;
    color: #8a7a68;
  }
</style>
