export const sealViewTemplate = `
<section class="panel">
  <h2>闸代快照</h2>
  <p class="hint">仅允许当前晋升票封闸升代；旧代/影子票不得再出快照。清单摘要供提单册对账引用。</p>
  <div class="form-row">
    <div><label>过磅票</label>
      <select v-model.number="sealForm.ticket_id">
        <option v-for="t in sealableTickets" :key="t.id" :value="t.id">{{ t.ticket_code }}</option>
      </select>
    </div>
    <div><label>清单(可空)</label><input v-model="sealForm.manifest"/></div>
  </div>
  <div class="actions">
    <button @click="createSeal">写入快照</button>
    <button class="secondary" @click="refresh">刷新</button>
  </div>
  <table class="data-table">
    <thead><tr><th>快照号</th><th>票号</th><th>闸代</th><th>清单摘要</th><th>状态</th><th>命运条</th></tr></thead>
    <tbody>
      <tr v-for="s in seals" :key="s.id">
        <td>{{ s.seal_ref }}</td>
        <td>{{ s.ticket_code }}</td>
        <td>{{ s.ticket_generation }}</td>
        <td class="mono">{{ shortText(s.manifest) }}</td>
        <td><span class="badge pass">{{ s.status }}</span></td>
        <td>
          <span v-if="sealFate(s)" class="badge"
                :class="sealFate(s).chain_ok ? 'pass' : 'fail'">
            {{ sealFate(s).chain_ok ? '当前第 ' + sealFate(s).current_generation + ' 代' : '偏航' }}
          </span>
          <span v-else class="badge muted">无命运</span>
          <span v-if="sealFate(s) && sealFate(s).current_generation !== s.ticket_generation"
                class="badge fail">旧代快照</span>
        </td>
      </tr>
    </tbody>
  </table>
</section>
`;
