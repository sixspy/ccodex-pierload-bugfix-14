export const ticketsViewTemplate = `
<section class="panel">
  <h2>过磅票采集</h2>
  <p class="hint">录入各轴重 JSON；同车再磅同事务作废旧票升新代，超重自动旁路挂起。</p>
  <div class="form-row">
    <div><label>车道</label>
      <select v-model.number="ticketForm.lane_id">
        <option v-for="l in lanes" :key="l.id" :value="l.id">{{ l.lane_code }}</option>
      </select>
    </div>
    <div><label>提单号</label>
      <select v-model="ticketForm.bl_ref">
        <option v-for="b in blList" :key="b.bl_code" :value="b.bl_code">{{ b.bl_code }}</option>
      </select>
    </div>
    <div><label>车牌</label><input v-model="ticketForm.vehicle_plate"/></div>
    <div><label>票号(可空)</label><input v-model="ticketForm.ticket_code"/></div>
  </div>
  <label>轴重 JSON</label>
  <textarea v-model="ticketForm.axles_json" rows="4" placeholder='[{"axle":1,"w":8.2}]'></textarea>
  <p v-if="ticketForm.vehicle_plate && fateOf(ticketForm.vehicle_plate)" class="hint">
    命运条：
    <span class="badge" :class="fateOf(ticketForm.vehicle_plate).chain_ok ? 'pass' : 'fail'">
      {{ fateOf(ticketForm.vehicle_plate).chain_ok ? '单正式' : '偏航拒写' }}
    </span>
    当前正式 {{ fateOf(ticketForm.vehicle_plate).current_ticket_code || '—' }}
    · G{{ fateOf(ticketForm.vehicle_plate).current_generation || '—' }}
    · 作废 {{ fateOf(ticketForm.vehicle_plate).voided_ticket_codes.length }} 张
    <span v-if="!fateOf(ticketForm.vehicle_plate).chain_ok" class="bad">
      {{ fateOf(ticketForm.vehicle_plate).issues.join('；') }}
    </span>
  </p>
  <div class="actions">
    <button @click="createTicket">过磅入闸</button>
    <button class="secondary" @click="refresh">刷新</button>
  </div>
  <table class="data-table">
    <thead><tr><th>票号</th><th>车道</th><th>车牌</th><th>提单</th><th>毛重</th><th>状态</th><th>代</th><th>命运条</th><th></th></tr></thead>
    <tbody>
      <tr v-for="t in tickets" :key="t.id" @click="selectTicket(t)">
        <td>{{ t.ticket_code }}</td>
        <td>{{ t.lane_code }}</td>
        <td>{{ t.vehicle_plate }}</td>
        <td>{{ t.bl_ref }}</td>
        <td>{{ fmtT(t.gross_t) }}</td>
        <td><span class="badge" :class="ticketClass(t.status)">{{ t.status }}</span></td>
        <td>{{ t.generation }}</td>
        <td><span class="badge" :class="fateClass(t)">{{ fateBadge(t) }}</span></td>
        <td><button class="mini-btn" @click.stop="loadTicketDetail(t.id)">详情</button></td>
      </tr>
    </tbody>
  </table>
  <div v-if="ticketDetail" class="detail-box">
    <p>车牌 {{ ticketDetail.ticket.vehicle_plate }} · 超重挂起 {{ ticketDetail.overload_holds.length }} 条</p>
    <p v-if="ticketFate(ticketDetail.ticket)">
      同车正式 {{ ticketFate(ticketDetail.ticket).formal_count }} 张
      · 当前 {{ ticketFate(ticketDetail.ticket).current_ticket_code || '—' }}
      · {{ ticketFate(ticketDetail.ticket).chain_ok ? '链路闭合' : '偏航：' + ticketFate(ticketDetail.ticket).issues.join('；') }}
    </p>
  </div>
</section>
`;
