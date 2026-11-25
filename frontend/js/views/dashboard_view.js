export const dashboardViewTemplate = `
<section class="panel">
  <h2>闸口总览</h2>
  <p class="hint">过磅票入闸后裁定超重才放行，驳回进旁路挂起；同车二次过磅须同事务作废旧票升新代，闸代快照须与提单册对账。</p>
  <div class="hero-cards">
    <div class="hero-card"><span class="t">地磅桥</span><div class="n">{{ dash.bridges ?? '—' }}</div></div>
    <div class="hero-card"><span class="t">开放超重</span><div class="n">{{ dash.open_overloads ?? '—' }}</div></div>
    <div class="hero-card"><span class="t">旁路挂起</span><div class="n">{{ dash.side_pending ?? '—' }}</div></div>
    <div class="hero-card"><span class="t">过磅票</span><div class="n">{{ dash.tickets ?? '—' }}</div></div>
    <div class="hero-card"><span class="t">已放行</span><div class="n">{{ dash.gate_releases ?? '—' }}</div></div>
    <div class="hero-card"><span class="t">已封闸</span><div class="n">{{ dash.gate_seals ?? '—' }}</div></div>
  </div>
  <div class="detail-box">
    <p>
      升代命运条：单车 <strong>{{ fateSummary.total }}</strong> 辆 ·
      单正式 <strong>{{ fateSummary.ok }}</strong> ·
      <span :class="fateSummary.hasDrift ? 'bad' : 'ok'">
        偏航 {{ fateSummary.drift }}
      </span>
    </p>
    <p v-if="fateSummary.hasDrift" class="bad">
      同车双正式/旧票漏废须先修命运条，系统将拒写新业务。
    </p>
  </div>
  <p class="hint" style="margin-top:16px">骨架：{{ dash.meta && dash.meta.skeleton }}</p>
</section>
`;
