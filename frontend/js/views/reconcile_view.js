export const reconcileViewTemplate = `
<section class="grid-2">
  <section class="panel">
    <h2>提单对账</h2>
    <p class="hint">只计当前正式票；作废票与未晋升影子票不得并入合计，同车双正式单列拒平。</p>
    <div class="form-row">
      <div><label>提单号</label><input v-model="reconCode"/></div>
    </div>
    <div class="actions">
      <button @click="loadReconcile">对账</button>
      <button class="secondary" @click="loadAllReconcile">全量</button>
    </div>
    <div v-if="reconOne" class="detail-box">
      <p>申报 {{ reconOne.declared_gross_t }}t · 过磅合计 {{ reconOne.ticket_sum_t }}t</p>
      <p :class="reconOne.balanced ? 'ok' : 'bad'">{{ reconOne.balanced ? '账实平衡' : '偏差待查' }}</p>
      <p>快照数 {{ reconOne.seal_count }} · 可出证明 {{ reconOne.proof_ready ? '是' : '否' }}</p>
      <p v-if="reconOne.double_formal && reconOne.double_formal.length" class="bad">
        同车双正式拒平：
        <span v-for="d in reconOne.double_formal" :key="d.vehicle_plate">
          {{ d.vehicle_plate }}（{{ d.ticket_codes.join('、') }}）
        </span>
      </p>
      <p v-if="reconOne.stale_seals && reconOne.stale_seals.length" class="bad">
        旧代快照 {{ reconOne.stale_seals.length }} 张（须按当前代重封）
      </p>
      <p v-if="reconOne.voided_tickets && reconOne.voided_tickets.length" class="hint">
        已作废不计：{{ voidedCodes(reconOne.voided_tickets) }}
      </p>
    </div>
    <ul v-if="reconAllItems.length">
      <li v-for="r in reconAllItems" :key="r.bl_code">
        {{ r.bl_code }} · {{ r.balanced ? '平' : '偏' }}
        <span v-if="r.double_formal && r.double_formal.length" class="bad">（双正式）</span>
      </li>
    </ul>
  </section>
  <section class="panel">
    <h2>单票证明</h2>
    <div class="form-row"><div><label>票号</label><input v-model="proofCode"/></div></div>
    <div class="actions"><button @click="loadProof">拉证明</button></div>
    <div v-if="proofOne" class="detail-box">
      <p>提单匹配 {{ proofOne.manifest_matches_bl ? '是' : '否' }}</p>
      <p>超重闭环 {{ proofOne.overload_closed ? '是' : '否' }}</p>
      <p>已放行 {{ proofOne.released ? '是' : '否' }}</p>
      <p v-if="proofOne.fate">
        命运条 {{ proofOne.fate.chain_ok ? '闭合' : '偏航' }}
        · 正式 {{ proofOne.fate.formal_count }} 张
        <span v-if="!proofOne.fate.chain_ok" class="bad">（{{ proofOne.fate.issues.join('；') }}）</span>
      </p>
      <p v-if="proofOne.voided" class="bad">该票已作废，不得出证明</p>
      <p>一致 {{ proofOne.coherent ? '是' : '否' }}</p>
    </div>
  </section>
</section>
`;
