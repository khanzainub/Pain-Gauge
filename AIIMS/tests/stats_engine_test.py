"""Reference and guardrail tests. Synthetic data only; never app demonstration data."""
import unittest,sys,json,copy,math,base64,io,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import importlib.util
sp=importlib.util.spec_from_file_location('engine',Path(__file__).resolve().parents[1]/'care-stats-engine.py');e=importlib.util.module_from_spec(sp);sp.loader.exec_module(e)
import numpy as np,pandas as pd
from scipy import stats
from statsmodels.stats.contingency_tables import StratifiedTable,SquareTable
from statsmodels.stats.multitest import multipletests
META=[{'key':'painScore','label':'Pain','type':'ordinal','order':list(range(11))},{'key':'sleepQuality','label':'Sleep','type':'ordinal','order':['Very poor','Poor / interrupted','Average','Restful']},{'key':'gender','label':'Sex','type':'nominal'},{'key':'diagnosis','label':'Disease','type':'nominal'},{'key':'mood','label':'Mood','type':'nominal'},{'key':'ageGroup','label':'Age group','type':'ordinal','order':['18–29','30–44','45–59']},{'key':'sleepHours','label':'Sleep hours','type':'numeric'},{'key':'medicine:NSAID','label':'Medication · NSAID','type':'binary','order':['Not selected','Selected']}]
def payload(model,rows,outcome='painScore',predictors=None,**opts):
    for i,r in enumerate(rows):r.setdefault('patient','P'+str(i));r.setdefault('date','2026-10-01')
    return {'rows':rows,'variables':copy.deepcopy(META),'spec':{'model':model,'outcome':outcome,'predictors':predictors if predictors is not None else ['gender'],'unit':'daily' if model in e.PAIRED or model.startswith('gee') else 'latest','correction':'holm',**opts},'audit':{'sourceEntries':len(rows)}}
def table_rows(t):return [{'gender':a,'diagnosis':b} for i,row in enumerate(t) for j,n in enumerate(row) for _ in range(n) for a,b in [(f'G{i}',f'D{j}')]]
def paired_rows(values,outcome='painScore'):
    return [{'patient':'P'+str(i),'date':'2026-10-'+str(j+1).zfill(2),outcome:v} for i,vs in enumerate(values) for j,v in enumerate(vs)]
class AssessmentTests(unittest.TestCase):
    def test_fisher_documented_reference(self):
        r=e.analyse(payload('fisher',table_rows([[6,2],[1,4]]),'diagnosis',['gender']));self.assertAlmostEqual(r['p'],0.10256410256410256);self.assertAlmostEqual(r['estimate'],12)
    def test_pearson_g_cramer_phi(self):
        t=np.array([[20,40],[30,10]])
        for model in ['chi2','gtest','cramer','phi']:
            r=e.analyse(payload(model,table_rows(t),'diagnosis',['gender']));ref=stats.chi2_contingency(t,correction=False,lambda_='log-likelihood' if model=='gtest' else None);self.assertAlmostEqual(r['p'],ref.pvalue)
            if model=='phi':self.assertAlmostEqual(r['estimate'],np.linalg.det(t)/np.sqrt(np.prod(t.sum(axis=0))*np.prod(t.sum(axis=1))))
    def test_sparse_table_blocks_asymptotic_but_monte_carlo_reproducible(self):
        p=payload('chi2',table_rows([[5,0,1],[0,4,2]]),'diagnosis',['gender'])
        with self.assertRaisesRegex(e.EligibilityError,'Sparse'):e.analyse(p)
        p['spec']['model']='ffh';a=e.analyse(p);b=e.analyse(p);self.assertEqual(a['p'],b['p']);self.assertGreater(a['p'],0);self.assertEqual(a['resampling']['replicates'],9999)
    def test_spearman_kendall_gamma_somers_with_ties(self):
        a=np.array([1,1,2,2,3,3,4,4]);b=np.array([1,2,1,2,3,3,4,3]);rows=[{'painScore':int(x),'sleepHours':int(y)} for x,y in zip(b,a)]
        for m,fn in [('spearman',lambda:stats.spearmanr(a,b).statistic),('kendall',lambda:stats.kendalltau(a,b).statistic),('somers',lambda:stats.somersd(a,b).statistic)]:
            r=e.analyse(payload(m,copy.deepcopy(rows),'painScore',['sleepHours']));self.assertAlmostEqual(r['estimate'],fn());self.assertTrue(0<=r['p']<=1)
        # Independent exhaustive pair-count reference for gamma.
        c=d=0
        for i,j in itertools.combinations(range(len(a)),2):
            v=np.sign(a[i]-a[j])*np.sign(b[i]-b[j]);c+=v>0;d+=v<0
        self.assertAlmostEqual(e.gamma_stat(a,b),(c-d)/(c+d))
    def test_nominal_codes_not_accepted_as_ordered(self):
        with self.assertRaisesRegex(e.EligibilityError,'defined order'):e.analyse(payload('spearman',[{'painScore':i%5,'gender':['Male','Female'][i%2]} for i in range(20)]))
    def test_mann_whitney_known_exact(self):
        r=e.analyse(payload('mann',[{'painScore':v,'gender':'A' if v<4 else 'B'} for v in range(1,7)]));self.assertEqual(r['statistic'],0);self.assertAlmostEqual(r['p'],.1);self.assertEqual(r['estimate'],-1)
    def test_kruskal_dunn_matches_validated_reference(self):
        import scikit_posthocs as ph
        vals=[1,2,2,3,4,2,3,4,5,6,4,5,6,7,8];groups=['a']*5+['b']*5+['c']*5;rows=[{'painScore':v,'gender':g} for v,g in zip(vals,groups)]
        r=e.analyse(payload('dunn',rows));reference=ph.posthoc_dunn(pd.DataFrame({'value':vals,'group':groups}),val_col='value',group_col='group',p_adjust=None)
        for c,(i,j) in zip(r['comparisons'],itertools.combinations(['a','b','c'],2)):self.assertAlmostEqual(c['p'],reference.loc[i,j])
        ref=stats.kruskal(vals[:5],vals[5:10],vals[10:]);self.assertAlmostEqual(r['statistic'],ref.statistic)
    def test_jonckheere_statistic_against_bruteforce(self):
        a=np.array([0,0,1,1,2,2]);b=np.array([1,2,2,3,3,4]);expected=sum(1 if b[i]<b[j] else .5 if b[i]==b[j] else 0 for i in range(len(a)) for j in range(len(a)) if a[i]<a[j]);self.assertEqual(e.jt_stat(a,b),expected)
        r=e.analyse(payload('jt',[{'painScore':int(v),'ageGroup':['18–29','30–44','45–59'][g]} for g,v in zip(a,b)],'painScore',['ageGroup']));self.assertTrue(0<r['p']<1)
    def test_cmh_matches_statsmodels(self):
        tables=[np.array([[15,10],[5,20]]),np.array([[12,8],[7,23]])];rows=[]
        for k,t in enumerate(tables):
            for r in table_rows(t):r['mood']='S'+str(k);rows.append(r)
        r=e.analyse(payload('cmh',rows,'diagnosis',['gender'],stratum='mood'));ref=StratifiedTable(np.stack(tables,axis=2));self.assertAlmostEqual(r['estimate'],ref.oddsratio_pooled);self.assertAlmostEqual(r['p'],ref.test_null_odds().pvalue)
    def test_categorical_trend(self):
        rows=[{'ageGroup':['18–29','30–44','45–59'][i],'gender':g} for i,counts in enumerate([[20,5],[15,15],[5,20]]) for j,n in enumerate(counts) for _ in range(n) for g in [['Female','Male'][j]]]
        r=e.analyse(payload('ca',rows,'gender',['ageGroup'],positive='Male'));self.assertLess(r['p'],.001)
    def test_matched_tests_and_patient_counts(self):
        values=[[1+(i%3),2+(i%3),3+(i%3)] for i in range(12)];dates=['2026-10-01','2026-10-02','2026-10-03'];p=payload('friedman',paired_rows(values),predictors=[],dates=dates);r=e.analyse(p);self.assertEqual(r['patients'],12);self.assertEqual(r['observations'],36);self.assertAlmostEqual(r['statistic'],stats.friedmanchisquare(*np.array(values).T).statistic)
        p=payload('sign',paired_rows([v[:2] for v in values]),predictors=[],dates=dates[:2]);r=e.analyse(p);self.assertAlmostEqual(r['p'],2/2**12)
        p['spec'].update(model='wilcoxon',symmetryConfirmed=True);r=e.analyse(p);self.assertGreaterEqual(r['p'],0)
        p['spec']['symmetryConfirmed']=False
        with self.assertRaisesRegex(e.EligibilityError,'symmetr'):e.analyse(p)
    def test_incomplete_dates_and_outside_dates_not_counted_as_complete_patients(self):
        rows=paired_rows([[1,2,3] for _ in range(6)]+[[1,2] for _ in range(2)])
        r=e.analyse(payload('sign',rows,predictors=[],dates=['2026-10-01','2026-10-03']));self.assertEqual(r['patients'],6);self.assertEqual(r['observations'],12);self.assertEqual(r['excludedUnmatchedPatients'],2)
    def test_binary_matched_tests(self):
        values=[['Female','Male']]*8+[['Male','Female']]*2+[['Male','Male']]*4+[['Female','Female']]*4
        r=e.analyse(payload('mcnemar',paired_rows(values,'gender'),'gender',[],dates=['2026-10-01','2026-10-02'],positive='Male'));self.assertAlmostEqual(r['p'],stats.binomtest(2,10,.5).pvalue)
        values=[['Female','Male','Male'],['Male','Female','Male'],['Female','Female','Male'],['Male','Male','Female']]*5
        r=e.analyse(payload('cochranq',paired_rows(values,'gender'),'gender',[],dates=['2026-10-01','2026-10-02','2026-10-03']));self.assertTrue(np.isfinite(r['p']))
    def test_stuart_and_bowker_symmetric_reference(self):
        values=[[a,b] for i,a in enumerate(['a','b','c']) for j,b in enumerate(['a','b','c']) for _ in range(20 if i==j else 10)]
        for m in ['stuart','bowker']:
            r=e.analyse(payload(m,paired_rows(values,'mood'),'mood',[],dates=['2026-10-01','2026-10-02']));self.assertAlmostEqual(r['p'],1)
    def test_mca_matches_prince_eigenvalues(self):
        import prince
        rows=table_rows([[20,10,5],[10,25,5],[5,10,25]]);p=payload('mca',rows,'diagnosis',['gender']);r=e.analyse(p);ref=prince.MCA(n_components=2,engine='scipy').fit(pd.DataFrame(rows)[['diagnosis','gender']]);np.testing.assert_allclose(r['eigenvalues'][:2],ref.eigenvalues_,rtol=1e-7)
    def test_loglinear_matches_pearson_likelihood_ratio_for_two_variables(self):
        rows=table_rows([[20,40],[30,10]]);r=e.analyse(payload('loglinear',rows,'diagnosis',['gender']));ref=stats.chi2_contingency([[20,40],[30,10]],correction=False,lambda_='log-likelihood');self.assertAlmostEqual(r['statistic'],ref.statistic,places=6)
    def test_binary_adjusted_regression_known_coefficients_and_interactions(self):
        rng=np.random.default_rng(77);n=1400;x=rng.integers(0,2,n);z=rng.integers(0,2,n);pr=1/(1+np.exp(-(-1+.7*x+.5*z+.6*x*z)));y=rng.binomial(1,pr)
        rows=[{'gender':['Female','Male'][a],'mood':['Calm','Anxious'][b],'medicine:NSAID':['Not selected','Selected'][c]} for a,b,c in zip(x,z,y)];r=e.analyse(payload('binary',rows,'medicine:NSAID',['gender','mood'],interaction=True,positive='Selected'));self.assertEqual(len(r['estimates']),3);self.assertTrue(r['converged']);self.assertAlmostEqual(math.log(r['estimates'][0]['estimate']),1.3,delta=.45)
    def test_ordinal_adjusted_regression_and_assumption_check(self):
        rows=[]
        for x in [0,1]:
            cumulative=1/(1+np.exp(-(np.array([-1,.5,1.5])-.6*x)));counts=np.diff(np.r_[0,np.round(cumulative*1000).astype(int),1000])
            for y,n in enumerate(counts):rows += [{'gender':['Female','Male'][x],'painScore':y} for _ in range(n)]
        r=e.analyse(payload('ordinal',rows));self.assertAlmostEqual(math.log(r['estimates'][0]['estimate']),.6,delta=.25);self.assertGreater(r['diagnostic']['p'],.05)
    def test_multinomial_regression(self):
        rng=np.random.default_rng(9);rows=[{'gender':['Female','Male'][i%2],'mood':rng.choice(['Calm','Anxious','Happy'])} for i in range(600)];r=e.analyse(payload('multinomial',rows,'mood',['gender']));self.assertEqual(len(r['estimates']),2)
    def test_gee_clusters_not_independent_rows(self):
        rng=np.random.default_rng(24);rows=[]
        for i in range(100):
            x=i%2;random=rng.normal(0,.5)
            for j in range(3):
                y=int(rng.binomial(1,1/(1+np.exp(-(-.5+.4*x+random)))));rows.append({'patient':'P'+str(i),'date':'2026-10-0'+str(j+1),'gender':['Female','Male'][x],'medicine:NSAID':['Not selected','Selected'][y]})
        r=e.analyse(payload('geeBinary',copy.deepcopy(rows),'medicine:NSAID',['gender']));self.assertEqual(r['patients'],100);self.assertEqual(r['observations'],300)
        p=payload('binary',rows,'medicine:NSAID',['gender'])
        with self.assertRaisesRegex(e.EligibilityError,'Repeated'):e.analyse(p)
    def test_ordinal_gee(self):
        rng=np.random.default_rng(90);rows=[]
        for i in range(120):
            x=i%2;z=rng.normal(0,.3)
            for j in range(3):rows.append({'patient':'P'+str(i),'date':'2026-10-0'+str(j+1),'gender':['Female','Male'][x],'painScore':int(np.digitize(.7*x+z+rng.logistic(),[-1,.5,1.5]))})
        r=e.analyse(payload('geeOrdinal',rows));self.assertEqual(len(r['estimates']),1);self.assertEqual(r['patients'],120)
    def test_regression_insufficient_variation_and_unsupported_models(self):
        rows=[{'painScore':i%3,'gender':['Male','Female'][i%2]} for i in range(10)]
        with self.assertRaisesRegex(e.EligibilityError,'Insufficient patients'):e.analyse(payload('ordinal',rows))
        for m in e.UNSUPPORTED:
            with self.assertRaisesRegex(e.EligibilityError,'validated'):e.analyse(payload(m,rows))
        with self.assertRaisesRegex(e.EligibilityError,'variation'):e.analyse(payload('chi2',[{'diagnosis':'uSpA','gender':'Female'} for i in range(20)],'diagnosis',['gender']))
    def test_multiplicity_matches_statsmodels_and_strata(self):
        r={'p':.03,'comparisons':[{'p':.01},{'p':.04}], 'diagnostic':{'p':.001}};n=e.adjust_family(r,'holm');self.assertEqual(n,3);np.testing.assert_allclose([r['adjustedP']]+[p['adjustedP'] for p in r['comparisons']],multipletests([.03,.01,.04],method='holm')[1]);self.assertNotIn('adjustedP',r['diagnostic'])
        rows=table_rows([[20,40],[30,10]])
        for i,row in enumerate(rows):row['mood']='S'+str(i%2)
        r=e.analyse(payload('chi2',rows,'diagnosis',['gender'],stratum='mood'));self.assertEqual(len(r['strata']),2)
    def test_exports_open_and_do_not_include_patient_level_rows(self):
        import openpyxl
        from pypdf import PdfReader
        r=e.analyse(payload('fisher',table_rows([[6,2],[1,4]]),'diagnosis',['gender']));source=json.dumps(r)
        csv=base64.b64decode(e.export_file(source,'csv')).decode('utf-8-sig');self.assertIn('Suppressed: small-cell',csv);self.assertNotIn('P0',csv)
        data=base64.b64decode(e.export_file(source,'xlsx'));wb=openpyxl.load_workbook(io.BytesIO(data));self.assertEqual(wb.active['A1'].value,'Pain Gauge · Statistical Assessment');self.assertGreater(wb.active.max_row,20)
        pdf=base64.b64decode(e.export_file(source,'pdf'));reader=PdfReader(io.BytesIO(pdf));self.assertGreaterEqual(len(reader.pages),1);self.assertIn('STATISTICAL ASSESSMENT',reader.pages[0].extract_text())
    def test_missing_is_not_zero_and_json_returns_explicit_failure(self):
        rows=[{'painScore':i%3,'gender':['Male','Female'][i%2]} for i in range(30)];rows[0]['painScore']=None;r=e.analyse(payload('mann',rows));self.assertEqual(r['excludedMissing'],1);self.assertEqual(r['observations'],29);self.assertEqual(r['missingByVariable']['Pain'],1)
        p=payload('binary',rows);p['spec']['outcome']='invented';self.assertFalse(json.loads(e.main_json(json.dumps(p)))['ok'])
if __name__=='__main__':unittest.main(verbosity=2)
