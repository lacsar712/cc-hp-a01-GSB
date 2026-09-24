<script>
  import { api } from './api.js'
  import RecordsPage from './RecordsPage.svelte'
  import RegisterPage from './RegisterPage.svelte'

  let username = localStorage.getItem('herb_username') || 'processor'
  let password = 'herb123456'
  let token = localStorage.getItem('herb_token') || ''
  let role = localStorage.getItem('herb_role') || ''
  let view = 'records'
  let loginError = ''

  async function enter() {
    loginError = ''
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      token = data.access_token
      role = data.role
      localStorage.setItem('herb_token', token)
      localStorage.setItem('herb_role', role)
      localStorage.setItem('herb_username', data.username)
    } catch (err) {
      loginError = err.message
    }
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
  }
</script>

{#if !token}
  <main class="login">
    <h1>饮片炮制记录台</h1>
    <p>炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。开炒前必须先在辅料批号册登记批号，写文书时从册中点选。</p>
    <div class="login-form">
      <input bind:value={username} placeholder="用户名" />
      <input type="password" bind:value={password} placeholder="密码" />
      <button on:click={enter}>登录</button>
    </div>
    {#if loginError}<p class="err">{loginError}</p>{/if}
    <p class="hint">processor / herb123456 可写；checker / check123456 只读</p>
  </main>
{:else}
  <header class="topbar">
    <span class="brand">饮片炮制记录台</span>
    <nav>
      <button class:active={view === 'records'} on:click={() => (view = 'records')}>炮制记录</button>
      <button class:active={view === 'register'} on:click={() => (view = 'register')}>辅料批号册</button>
    </nav>
    <span class="who">{role === 'writer' ? '炮制员' : '质检员'} · {username}</span>
    <button class="ghost" on:click={leave}>退出</button>
  </header>
  {#if view === 'records'}
    <RecordsPage {role} />
  {:else}
    <RegisterPage {role} />
  {/if}
{/if}

<style>
  :global(body) {
    margin: 0;
    font-family: sans-serif;
    color: #3f2f1f;
    background: #faf7f2;
  }
  .login {
    max-width: 720px;
    margin: 24px auto;
    padding: 0 16px;
  }
  .login h1 {
    color: #7c2d12;
  }
  .login-form {
    display: flex;
    gap: 8px;
  }
  .hint {
    color: #8a7a68;
    font-size: 13px;
  }
  .err {
    color: #b91c1c;
  }
  .topbar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 0 20px;
    height: 52px;
    background: #7c2d12;
    color: #fff7ed;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .brand {
    font-weight: 700;
    font-size: 17px;
  }
  .topbar nav {
    display: flex;
    gap: 4px;
    flex: 1;
  }
  .topbar button {
    background: transparent;
    border: none;
    color: #f5d9c4;
    padding: 8px 14px;
    font-size: 14px;
    cursor: pointer;
    border-radius: 6px;
  }
  .topbar button:hover {
    background: rgba(255, 255, 255, 0.12);
  }
  .topbar button.active {
    background: #fff7ed;
    color: #7c2d12;
    font-weight: 600;
  }
  .who {
    font-size: 13px;
    color: #f5d9c4;
  }
</style>
