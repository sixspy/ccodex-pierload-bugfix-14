export const lanesViewTemplate = `
<section class="panel">
  <h2>过磅车道</h2>
  <p class="hint">每车道配置超限阈值与旁路引用；进闸方向与出闸方向分开编码。车道页命运条与过磅页同源。</p>
  <div class="form-row">
    <div><label>车道编码</label><input v-model="laneForm.lane_code"/></div>
    <div><label>所属地磅</label>
      <select v-model.number="laneForm.bridge_id">
        <option v-for="b in bridges" :key="b.id" :value="b.id">{{ b.bridge_code }}</option>
      </select>
    </div>
    <div><label>方向</label><input v-model="laneForm.direction" placeholder="进闸/出闸"/></div>
    <div><label>超限阈值(吨)</label><input v-model.number="laneForm.overload_threshold_t" type="number"/></div>
    <div><label>旁路</label><input v-model="laneForm.side_lane_ref"/></div>
  </div>
  <div class="actions">
    <button @click="createLane">开通车道</button>
    <button class="secondary" @click="refresh">刷新</button>
  </div>
  <table class="data-table">
    <thead><tr><th>车道</th><th>地磅</th><th>方向</th><th>阈值</th><th>旁路</th><th>状态</th><th>在道正式票</th><th>命运条</th></tr></thead>
    <tbody>
      <tr v-for="l in lanes" :key="l.id">
        <td>{{ l.lane_code }}</td>
        <td>{{ l.bridge_code }}</td>
        <td>{{ l.direction }}</td>
        <td>{{ l.overload_threshold_t }}t</td>
        <td>{{ l.side_lane_ref || '—' }}</td>
        <td><span class="badge pass">{{ l.status }}</span></td>
        <td>{{ laneFormalCount(l.id) }}</td>
        <td>
          <span v-if="laneFateIssues(l.id).length" class="badge fail">
            偏航 {{ laneFateIssues(l.id).length }} 车
          </span>
          <span v-else class="badge pass">单正式</span>
        </td>
      </tr>
    </tbody>
  </table>
  <div v-for="l in lanes" :key="'iss'+l.id">
    <div v-if="laneFateIssues(l.id).length" class="detail-box">
      <p class="bad">{{ l.lane_code }} 升代命运偏航（须同事务作废旧票）：</p>
      <ul><li v-for="(x,i) in laneFateIssues(l.id)" :key="i">{{ x }}</li></ul>
    </div>
  </div>
</section>
`;
