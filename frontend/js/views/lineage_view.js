export const lineageViewTemplate = `
<section class="panel">
  <h2>轴重血缘</h2>
  <p class="hint">同车再磅的「二次升代」边由过磅事务自动落，不得手登记；此处只记驳载分票等其他边。</p>
  <div class="form-row">
    <div><label>起点票</label>
      <select v-model.number="lineageForm.from_ticket_id">
        <option v-for="t in tickets" :key="t.id" :value="t.id">{{ t.ticket_code }}</option>
      </select>
    </div>
    <div><label>终点票(可空)</label>
      <select v-model.number="lineageForm.to_ticket_id">
        <option :value="null">—</option>
        <option v-for="t in tickets" :key="t.id" :value="t.id">{{ t.ticket_code }}</option>
      </select>
    </div>
    <div><label>类型</label><input v-model="lineageForm.edge_type"/></div>
    <div><label>说明</label><input v-model="lineageForm.detail"/></div>
  </div>
  <div class="actions">
    <button @click="addLineage">登记边</button>
    <button class="secondary" @click="refresh">刷新</button>
  </div>
  <table class="data-table">
    <thead><tr><th>自</th><th>至</th><th>类型</th><th>说明</th></tr></thead>
    <tbody>
      <tr v-for="e in lineageEdges" :key="e.id">
        <td>{{ e.from_code || e.from_ticket_id }}</td>
        <td>{{ e.to_code || '—' }}</td>
        <td>{{ e.edge_type }}</td>
        <td>{{ e.detail }}</td>
      </tr>
    </tbody>
  </table>
  <h2 style="margin-top:18px">同车升代命运条</h2>
  <p class="hint">正式票唯一、旧票作废、升代接续完整；偏航即拒写并锁死当班。</p>
  <table class="data-table">
    <thead><tr><th>车牌</th><th>正式票</th><th>张数</th><th>当前代</th><th>作废票</th><th>链路</th><th>班次</th></tr></thead>
    <tbody>
      <tr v-for="f in fates" :key="f.vehicle_plate">
        <td>{{ f.vehicle_plate }}</td>
        <td>{{ f.current_ticket_code || '—' }}</td>
        <td>{{ f.formal_count }}</td>
        <td>G{{ f.current_generation || '—' }}</td>
        <td>{{ f.voided_ticket_codes.join('、') || '—' }}</td>
        <td>
          <span class="badge" :class="f.chain_ok ? 'pass' : 'fail'">
            {{ f.chain_ok ? '闭合' : '偏航' }}
          </span>
        </td>
        <td>
          <span v-if="f.shift_closed" class="badge muted">当班锁死</span>
          <span v-else-if="f.locked" class="badge pass">可再磅</span>
          <span v-else class="badge fail">拒写</span>
        </td>
      </tr>
    </tbody>
  </table>
  <div v-if="fateIssueRows().length" class="detail-box">
    <p class="bad">命运条偏航明细（须先修旧票再写）：</p>
    <ul>
      <li v-for="(r,i) in fateIssueRows()" :key="i">
        {{ r.vehicle_plate }} · {{ r.ticket_code || '—' }} · {{ r.issues.join('；') }}
      </li>
    </ul>
  </div>
</section>
`;
