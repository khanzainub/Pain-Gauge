"""Pain Gauge assessment engine. SciPy / statsmodels, no network or patient identifiers.
All inference is exploratory; typed variables and observational units are checked here,
independently of the UI. Randomized inference uses the recorded fixed seed.
"""
import json, math, warnings, itertools, io, zipfile, textwrap, hashlib
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import scipy
from scipy import stats, linalg
import statsmodels
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.contingency_tables import Table, Table2x2, SquareTable, StratifiedTable, mcnemar, cochrans_q
from statsmodels.miscmodels.ordinal_model import OrderedModel
from statsmodels.genmod.generalized_estimating_equations import OrdinalGEE
from statsmodels.genmod.cov_struct import OrdinalIndependence, Exchangeable

SEED=20261018
B=9999
UNSUPPORTED={'polychoric','partial','clmm','mixedBinary'}
PAIRED={'friedman','sign','wilcoxon','mcnemar','cochranq','stuart','bowker'}
REGRESSION={'ordinal','binary','multinomial','geeOrdinal','geeBinary'}
ORDINAL={'ordinal','numeric'}

class EligibilityError(ValueError): pass

def require(test,message):
    if not test: raise EligibilityError(message)

def safe(obj):
    if isinstance(obj,dict): return {str(k):safe(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple,np.ndarray)): return [safe(v) for v in obj]
    if isinstance(obj,(np.integer,)): return int(obj)
    if isinstance(obj,(np.floating,float)): return float(obj) if np.isfinite(obj) else None
    return obj

def result(name,statistic=None,p=None,estimate=None,**kw):
    return {'method':name,'statistic':statistic,'p':p,'estimate':estimate,**kw}

def codes(series,meta):
    order=meta.get('order')
    if meta['type']=='numeric': return pd.to_numeric(series,errors='raise').astype(float).to_numpy()
    if order:
        require(set(series).issubset(set(order)),f"Unrecognized category for {meta['label']}.")
        return pd.Categorical(series,categories=order,ordered=True).codes
    require(meta['type'] not in ORDINAL,'Ordinal categories need an explicit order.')
    return pd.Categorical(series,categories=sorted(series.unique(),key=str)).codes

def binary_values(series,positive=None):
    levels=sorted(series.unique(),key=str)
    require(len(levels)==2,'Exactly two recorded outcome categories are required.')
    positive=positive if positive in levels else levels[-1]
    return (series==positive).astype(int).to_numpy(),positive,[v for v in levels if v!=positive][0]

def contingency(df,x,y,metadata):
    def levels(k):
        raw=list(df[k].unique()); order=metadata[k].get('order')
        return [v for v in order if v in raw] if order else sorted(raw,key=str)
    xs,ys=levels(x),levels(y)
    table=pd.crosstab(df[x],df[y]).reindex(index=xs,columns=ys,fill_value=0).to_numpy()
    require(min(table.shape)>=2,'Both variables need at least two recorded categories.')
    require(table.size<=200,'Too many contingency cells. Select broader recorded categories or fewer predictors.')
    return table,xs,ys

def gamma_stat(a,b):
    # Concordant/discordant counts from the ordinal contingency table; ties excluded.
    t=pd.crosstab(a,b).to_numpy();c=d=0
    for i,j in np.ndindex(t.shape):
        c+=t[i,j]*t[i+1:,j+1:].sum();d+=t[i,j]*t[i+1:,:j].sum()
    return (c-d)/(c+d) if c+d else np.nan

def jt_stat(group,outcome):
    val=0.
    for i,j in itertools.combinations(sorted(set(group)),2):
        a=outcome[group==i]; b=outcome[group==j]
        val+=np.sum(a[:,None]<b[None,:])+.5*np.sum(a[:,None]==b[None,:])
    return val

def permutation_association(a,b,fn,alternative='two-sided'):
    # Pairing permutations condition on observed marginal values and preserve ties.
    r=stats.permutation_test((np.asarray(a),),lambda shuffled:fn(shuffled,np.asarray(b)),permutation_type='pairings',n_resamples=B,alternative=alternative,random_state=SEED,vectorized=False)
    return float(r.pvalue)

def describe(df,keys,metadata):
    output=[]
    for key in keys:
        meta=metadata[key]
        counts=df[key].value_counts(dropna=False)
        output.append({'variable':meta['label'],'levels':[{'category':str(k),'n':int(v),'percent':100*int(v)/len(df)} for k,v in counts.items()]})
    return output

def design(df,predictors,metadata,interaction=False,constant=True):
    parts=[]; references={};groups={}
    for key in predictors:
        meta=metadata[key]
        if meta['type']=='numeric':
            vals=pd.to_numeric(df[key]).astype(float);part=pd.DataFrame({meta['label']:vals},index=df.index)
        else:
            order=meta.get('order') or sorted(df[key].unique(),key=str)
            levels=[v for v in order if v in set(df[key])]
            require(len(levels)>1,f"No variation in {meta['label']}.")
            references[meta['label']]=str(levels[0])
            cat=pd.Categorical(df[key],categories=levels)
            part=pd.get_dummies(cat,prefix=meta['label'],prefix_sep=': ',drop_first=True,dtype=float)
            part.index=df.index
        groups[key]=list(part.columns);parts.append(part)
    X=pd.concat(parts,axis=1)
    if interaction:
        require(len(predictors)==2,'Select exactly two predictors for a fully specified interaction model.')
        a,b=predictors
        for ca,cb in itertools.product(groups[a],groups[b]): X[ca+' × '+cb]=X[ca]*X[cb]
    if constant:X=sm.add_constant(X,has_constant='add')
    require(X.shape[1]<=35,'Model has too many parameters. Reduce categories, predictors or interactions.')
    require(np.linalg.matrix_rank(X.to_numpy())==X.shape[1],'Predictor matrix is rank deficient. Remove redundant or nested variables.')
    return X,references

def proportional_odds_check(y,X,patient):
    # Stacked cumulative logits; a patient-cluster robust Wald test compares slopes
    # across thresholds (not an invalid independent-observation likelihood ratio).
    levels=np.unique(y);q=len(levels)-1;p=X.shape[1];n=len(y)
    if q<=1:return {'status':'Not applicable: binary outcome.'}
    require(q*p<=45 and n>=max(40,5*q*p),'Not enough patients for the proportional-odds diagnostic; reduce outcome categories or use another model.')
    ys=np.concatenate([(y>cut).astype(int) for cut in levels[:-1]])
    Z=np.zeros((n*q,q+p*q))
    for j in range(q):
        Z[j*n:(j+1)*n,j]=1
        Z[j*n:(j+1)*n,q+j*p:q+(j+1)*p]=X.to_numpy()
    fit=sm.GLM(ys,Z,family=sm.families.Binomial()).fit(cov_type='cluster',cov_kwds={'groups':np.tile(np.asarray(patient),q)},maxiter=200)
    require(fit.converged and np.all(np.isfinite(fit.cov_params())),'Proportional-odds diagnostic failed to converge.')
    R=np.zeros(((q-1)*p,Z.shape[1]))
    for j in range(1,q):
        for k in range(p):R[(j-1)*p+k,q+k]=-1;R[(j-1)*p+k,q+j*p+k]=1
    cov=R@fit.cov_params()@R.T
    require(np.linalg.matrix_rank(cov)==len(R),'Proportional-odds diagnostic covariance is singular.')
    test=fit.wald_test(R,scalar=True)
    require(np.isfinite(test.pvalue),'Proportional-odds diagnostic is non-finite.')
    return {'statistic':float(test.statistic),'p':float(test.pvalue),'status':'Cluster-robust cumulative-logit slope equality test; no rejection does not establish the assumption.'}

def fit_model(df,spec,metadata):
    model=spec['model'];out=spec['outcome'];pred=spec['predictors'];is_gee=model.startswith('gee');is_ord=model in {'ordinal','geeOrdinal'}
    require(pred and len(pred)<=6,'Select one to six predictors.')
    require(out not in pred,'Outcome cannot also be a predictor.')
    require(not is_ord or metadata[out]['type']=='ordinal','Ordinal regression requires an explicitly ordered outcome.')
    require(model!='multinomial' or metadata[out]['type'] in {'nominal','ordinal','binary'},'Multinomial regression requires a categorical outcome.')
    X,refs=design(df,pred,metadata,spec.get('interaction',False),constant=not is_ord)
    params=X.shape[1]+(df[out].nunique()-1 if is_ord else 0)
    if model=='multinomial':params=X.shape[1]*(df[out].nunique()-1)
    n_pat=df.patient.nunique()
    require(n_pat>=max(30,10*params),f'Insufficient patients for this model: need at least {max(30,10*params)} distinct patients for {params} parameters (conservative exploratory guardrail).')
    require(df.groupby(out).patient.nunique().min()>=max(5, X.shape[1] if model in {'binary','geeBinary','multinomial'} else 5),'Outcome categories are too sparse for stable regression.')
    assumptions=[]
    if is_gee:
        require(n_pat>=30 and (df.groupby('patient').size()>1).sum()>=20,'GEE needs at least 30 patient clusters, including 20 with repeated assessments.')
        assumptions.append('Patient-cluster robust sandwich covariance; at least 30 independent clusters. Daily rows use one representative entry per patient and date.')
    if is_ord:
        y=codes(df[out],metadata[out]);diag=proportional_odds_check(y,X,df.patient) if not is_gee else {'status':'Ordinal GEE assumes common cumulative slopes. Use sensitivity analyses; no formal proportional-odds diagnostic is supplied for correlated outcomes.'}
        if not is_gee:require(diag.get('p',1)>=.05,'Proportional-odds slope equality rejected (p='+str(round(diag['p'],5))+'). Common odds ratios are not reported. Consider multinomial regression.')
        fit=OrdinalGEE(y,X,df.patient,cov_struct=OrdinalIndependence()).fit(maxiter=200) if is_gee else OrderedModel(y,X,distr='logit').fit(method='bfgs',maxiter=500,disp=False)
    elif model=='multinomial':
        levels=sorted(df[out].unique(),key=str);require(len(levels)>=3,'Multinomial regression requires at least three categories.')
        y=pd.Categorical(df[out],categories=levels).codes;refs['Outcome']=str(levels[0]);fit=sm.MNLogit(y,X).fit(method='newton',maxiter=200,disp=False);diag=None
    else:
        y,positive,negative=binary_values(df[out],spec.get('positive'));refs['Outcome event']=str(positive);refs['Outcome reference']=str(negative);diag=None
        fit=sm.GEE(y,X,groups=df.patient,family=sm.families.Binomial(),cov_struct=Exchangeable()).fit(maxiter=200) if is_gee else sm.Logit(y,X).fit(method='newton',maxiter=200,disp=False)
    converged=fit.converged if is_gee else fit.mle_retvals.get('converged',False)
    require(converged,'Model did not converge. No estimates have been released.')
    require(np.all(np.isfinite(fit.params)) and np.all(np.isfinite(fit.bse)) and np.all(np.asarray(fit.bse)>0),'Model covariance is invalid; separation or non-identifiability may be present.')
    require(np.max(np.abs(np.asarray(fit.params)))<20 and np.max(np.asarray(fit.bse))<10,'Unstable or separated model: estimates are too extreme for reliable reporting.')
    estimates=[]
    if model=='multinomial':
        for j in range(fit.params.shape[1]):
            for i,term in enumerate(X.columns):
                if term=='const':continue
                beta=float(fit.params.iloc[i,j]);se=float(fit.bse.iloc[i,j]);estimates.append({'term':str(levels[j+1])+' vs '+str(levels[0])+': '+term,'estimate':math.exp(beta),'low':math.exp(beta-1.95996398454*se),'high':math.exp(beta+1.95996398454*se),'p':float(fit.pvalues.iloc[i,j]),'scale':'Relative-risk ratio'})
    else:
        names=fit.params.index if hasattr(fit.params,'index') else fit.model.exog_names
        for i,term in enumerate(names):
            if term not in X.columns or term=='const':continue
            beta=float(np.asarray(fit.params)[i]);se=float(np.asarray(fit.bse)[i]);estimates.append({'term':term,'estimate':math.exp(beta),'low':math.exp(beta-1.95996398454*se),'high':math.exp(beta+1.95996398454*se),'p':float(np.asarray(fit.pvalues)[i]),'scale':'Adjusted odds ratio'})
    if is_ord:assumptions.append('Odds ratios refer to higher recorded outcome categories. Ordered predictors are dummy-coded; equal category spacing is not assumed.')
    return result({'ordinal':'Proportional odds ordinal logistic regression','binary':'Binary logistic regression','multinomial':'Multinomial logistic regression','geeOrdinal':'Ordinal GEE (working independence)','geeBinary':'Binary GEE (exchangeable working correlation)'}[model],estimates=estimates,references=refs,converged=True,diagnostic=diag,assumptions=assumptions,parameters=params)

def run_test(df,spec,metadata):
    model=spec['model'];out=spec['outcome'];pred=spec.get('predictors',[])
    if model in REGRESSION:return fit_model(df,spec,metadata)
    if model in PAIRED:
        dates=sorted(set(spec.get('dates',[])))
        require(len(dates)>=2,'Select assessment dates explicitly; matching uses exact dates, not nearest visits.')
        pivot=df[df.date.isin(dates)].pivot(index='patient',columns='date',values=out).reindex(columns=dates)
        total=len(pivot);pivot=pivot.dropna();require(len(pivot)>=5,'Fewer than five complete matched patients on the selected dates.')
        if model not in {'friedman','cochranq'}:require(len(dates)==2,'This paired test requires exactly two dates.')
        else:require(len(dates)>=3,'This repeated-measures test requires at least three dates.')
        raw=pivot.to_numpy();info={'matchedPatients':len(pivot),'excludedIncompletePairs':total-len(pivot),'dates':dates}
        if model in {'mcnemar','cochranq'}:
            _,positive,_=binary_values(pd.Series(raw.ravel()),spec.get('positive'));a=(raw==positive).astype(int);info['event']=str(positive)
            if model=='mcnemar':
                t=np.zeros((2,2),int)
                for x,y in a:t[x,y]+=1
                r=mcnemar(t,exact=True,correction=False);return result('Exact McNemar test',float(r.statistic),float(r.pvalue),table=t.tolist(),rowLabels=['Not event','Event'],columnLabels=['Not event','Event'],**info)
            require(np.any(np.diff(a,axis=1)),'No within-patient binary changes.')
            r=cochrans_q(a);return result('Cochran Q',float(r.statistic),float(r.pvalue),**info)
        if model in {'stuart','bowker'}:
            cats=sorted(set(raw.ravel()),key=str);require(len(cats)>=2,'No category variation.')
            t=np.zeros((len(cats),len(cats)),int)
            for x,y in raw:t[cats.index(x),cats.index(y)]+=1
            if model=='stuart':
                require(len(cats)<=6,'Too many matched categories for this sample.')
                r=SquareTable(t,shift_zeros=False).homogeneity(method='stuart_maxwell')
            else:r=SquareTable(t,shift_zeros=False).symmetry(method='bowker')
            off=np.array([t[i,j]+t[j,i] for i,j in itertools.combinations(range(len(cats)),2)])
            require(np.all(off>=5),'Sparse discordant category pairs: asymptotic matched-category inference is not reliable.')
            require(np.isfinite(r.pvalue),'Singular matched table; marginal homogeneity cannot be estimated.')
            return result('Stuart–Maxwell marginal homogeneity' if model=='stuart' else 'Bowker symmetry',float(r.statistic),float(r.pvalue),table=t.tolist(),rowLabels=cats,columnLabels=cats,**info)
        require(metadata[out]['type'] in ORDINAL,'This paired test requires an ordered outcome.')
        a=np.column_stack([codes(pivot[d],metadata[out]) for d in dates]);info['medianByDate']=[{'date':d,'median':float(np.median(a[:,i]))} for i,d in enumerate(dates)]
        if model=='friedman':
            require(len(pivot)>=10,'Friedman asymptotic inference requires at least ten complete patients here.')
            r=stats.friedmanchisquare(*a.T);return result('Friedman test (tie corrected)',float(r.statistic),float(r.pvalue),estimate=float(r.statistic)/(len(a)*(len(dates)-1)),effect='Kendall W',**info)
        diff=a[:,1]-a[:,0];nz=diff[diff!=0];require(len(nz)>=5,'Fewer than five non-tied pairs.')
        if model=='sign':
            r=stats.binomtest(int(np.sum(nz>0)),len(nz),.5);ci=r.proportion_ci();return result('Exact paired sign test',int(np.sum(nz>0)),float(r.pvalue),estimate=float(np.mean(nz>0)),confidence=[ci.low,ci.high],effect='Proportion increasing among non-tied pairs',ties=int(np.sum(diff==0)),**info)
        require(spec.get('symmetryConfirmed') and out in {'painScore','sleepHours'},'Wilcoxon requires confirmation of symmetric differences and meaningful score spacing. Use the sign test for purely ordered categories.')
        r=stats.wilcoxon(diff,zero_method='wilcox',correction=False,method='approx');return result('Wilcoxon signed-rank (normal approximation, tie corrected)',float(r.statistic),float(r.pvalue),**info)
    require(pred,'Select a predictor or comparison variable.')
    x=pred[0];y=out
    if model in {'spearman','kendall','gamma','somers','jt','ca'}:
        require(len(df)<=2000,'Rank permutation assessment is limited to 2,000 independent patients per run in this browser.')
        require(metadata[x]['type'] in ORDINAL,'The predictor must have a defined order.')
        if model!='ca':require(metadata[y]['type'] in ORDINAL,'The outcome must have a defined order.')
        a=codes(df[x],metadata[x]);b=codes(df[y],metadata[y]) if model!='ca' else binary_values(df[y],spec.get('positive'))[0]
        if model=='spearman':est=float(stats.spearmanr(a,b).statistic);p=permutation_association(a,b,lambda v,w:stats.spearmanr(v,w).statistic);name='Spearman rank correlation (pairing-permutation inference)'
        elif model=='kendall':est=float(stats.kendalltau(a,b,variant='b').statistic);p=permutation_association(a,b,lambda v,w:stats.kendalltau(v,w,variant='b').statistic);name='Kendall tau-b (pairing-permutation inference)'
        elif model=='gamma':est=gamma_stat(a,b);p=permutation_association(a,b,gamma_stat);name='Goodman–Kruskal gamma (pairing-permutation inference)'
        elif model=='somers':
            # SciPy D(Y|X): first argument is the predictor X.
            est=float(stats.somersd(a,b).statistic);p=permutation_association(a,b,lambda v,w:stats.somersd(v,w).statistic);name='Somers D (outcome given predictor; permutation inference)'
        elif model=='jt':
            est=jt_stat(a,b);p=permutation_association(a,b,jt_stat,alternative='greater');name='Jonckheere–Terpstra (increasing trend; pairing permutation)'
        else:
            t,ls,cs=contingency(df,x,y,metadata);require(len(cs)==2,'Trend outcome must have two categories.');require(np.all(stats.contingency.expected_freq(t)>=5),'Sparse trend table: asymptotic Cochran–Armitage inference is disabled. Use the fixed-margin Monte Carlo independence alternative.')
            # Explicitly orient the event as the second column.
            _,event,_=binary_values(df[y],spec.get('positive'));col_scores=[int(c==event) for c in cs];row_scores=[metadata[x]['order'].index(l) if metadata[x].get('order') else float(l) for l in ls]
            r=Table(t,shift_zeros=False).test_ordinal_association(row_scores=np.array(row_scores),col_scores=np.array(col_scores));require(np.isfinite(r.pvalue),'No trend variance.');return result('Cochran–Armitage linear-by-linear trend',float(r.zscore),float(r.pvalue),event=str(event),assumptions=['Equally spaced rank scores for ordered groups; asymptotic normal approximation.'],table=t.tolist(),rowLabels=ls,columnLabels=cs)
        require(np.isfinite(est),'Association is undefined because all informative pairs are tied.')
        return result(name,p=p,estimate=est,resampling={'seed':SEED,'requestedPermutations':B,'alternative':'increasing' if model=='jt' else 'two-sided'},assumptions=['Independent patients. Permutations condition on observed ranks and ties. Gamma excludes ties and can overstate concordance.'] if model=='gamma' else ['Independent patients; recorded ordinal ordering.'],matrix={'x':a.tolist(),'y':b.tolist(),'xLabel':metadata[x]['label'],'yLabel':metadata[y]['label']})
    if model in {'mann','kruskal','dunn'}:
        require(metadata[y]['type'] in ORDINAL,'Group comparisons require an ordered outcome.')
        labels=sorted(df[x].unique(),key=str);groups=[codes(df.loc[df[x]==g,y],metadata[y]) for g in labels]
        require(min(map(len,groups))>=3,'At least three complete patients per group are required.')
        if model=='mann':
            require(len(groups)==2,'Mann–Whitney requires exactly two groups.')
            r=stats.mannwhitneyu(*groups,alternative='two-sided',method=stats.PermutationMethod(n_resamples=B,random_state=SEED));return result('Mann–Whitney U (permutation inference)',float(r.statistic),float(r.pvalue),estimate=2*float(r.statistic)/(len(groups[0])*len(groups[1]))-1,effect='Rank-biserial correlation (first group minus second)',groups=[{'group':str(g),'n':len(v),'medianRankScore':float(np.median(v))} for g,v in zip(labels,groups)])
        require(min(map(len,groups))>=5,'Kruskal–Wallis and Dunn require at least five complete patients per group here.')
        r=stats.kruskal(*groups);outcome=result('Kruskal–Wallis H (tie corrected)',float(r.statistic),float(r.pvalue),estimate=max(0,(float(r.statistic)-len(groups)+1)/(len(df)-len(groups))),effect='Epsilon-squared',groups=[{'group':str(g),'n':len(v),'medianRankScore':float(np.median(v))} for g,v in zip(labels,groups)])
        if model=='dunn':
            vals=codes(df[y],metadata[y]);ranks=stats.rankdata(vals);_,cnt=np.unique(vals,return_counts=True);n=len(vals);variance=n*(n+1)/12-np.sum(cnt**3-cnt)/(12*(n-1));comparisons=[]
            for i,j in itertools.combinations(labels,2):
                ra=ranks[np.asarray(df[x]==i)];rb=ranks[np.asarray(df[x]==j)];z=(ra.mean()-rb.mean())/np.sqrt(variance*(1/len(ra)+1/len(rb)));comparisons.append({'comparison':str(i)+' vs '+str(j),'statistic':float(z),'p':float(2*stats.norm.sf(abs(z)))})
            outcome.update(method='Dunn post-hoc comparisons with tie correction',statisticLabel='Omnibus Kruskal–Wallis H',omnibus={'method':'Kruskal–Wallis H','statistic':outcome['statistic'],'p':outcome['p']},comparisons=comparisons)
        return outcome
    if model in {'mca','loglinear'}:
        keys=list(dict.fromkeys([y]+pred));require(len(keys)>=2 and len(keys)<=4,'Choose two to four categorical variables.')
        require(all(metadata[k]['type']!='numeric' for k in keys),'This analysis requires categorical variables.')
        if model=='mca':
            Z=pd.get_dummies(df[keys].astype(str),dtype=float);require(Z.shape[1]<=60,'Too many categories for a compact MCA.')
            P=Z.to_numpy()/Z.to_numpy().sum();r=P.sum(axis=1);c=P.sum(axis=0);S=(P-np.outer(r,c))/np.sqrt(r[:,None]*c[None,:]);U,s,Vh=linalg.svd(S,full_matrices=False);eigen=s**2;require(len(s)>=2 and s[1]>1e-10,'Fewer than two informative MCA dimensions.')
            coordinates=(Vh.T[:,:2]*s[:2])/np.sqrt(c[:,None]);return result('Multiple correspondence analysis (complete indicator matrix, SVD)',eigenvalues=eigen[:5].tolist(),inertiaPercent=(100*eigen[:2]/eigen.sum()).tolist(),categories=[{'category':str(k),'x':float(v[0]),'y':float(v[1]),'n':int(Z[k].sum())} for k,v in zip(Z.columns,coordinates)],assumptions=['Exploratory, uncorrected inertia; no p-value. Rare categories can dominate coordinates. Distances do not establish a clinical association.'])
        import patsy
        data=df[keys].copy();data.columns=['v'+str(i) for i in range(len(keys))]
        index=pd.MultiIndex.from_product([sorted(data[k].unique(),key=str) for k in data],names=data.columns);counts=data.value_counts().reindex(index,fill_value=0).rename('count').reset_index()
        require(len(counts)<=100,'Too many joint categories for log-linear fitting.')
        require((counts['count']>=5).all(),'Sparse log-linear cells: select broader groups or more patients.')
        main=' + '.join('C('+k+')' for k in data);pair=' + '.join('C('+a+'):C('+b+')' for a,b in itertools.combinations(data.columns,2));base=patsy.dmatrix(main,counts,return_type='dataframe');full=patsy.dmatrix(main+' + '+pair,counts,return_type='dataframe')
        fit0=sm.GLM(counts['count'],base,family=sm.families.Poisson()).fit();fit1=sm.GLM(counts['count'],full,family=sm.families.Poisson()).fit();dof=full.shape[1]-base.shape[1];stat=2*(fit1.llf-fit0.llf);require(fit0.converged and fit1.converged,'Log-linear model did not converge.');return result('Poisson log-linear likelihood-ratio: main effects vs all two-way interactions',float(stat),float(stats.chi2.sf(stat,dof)),df=dof,deviance=float(fit1.deviance),assumptions=['Independent patient counts; no structural zeros specified. Tests all two-way associations jointly, not a causal model.'])
    t,ls,cs=contingency(df,x,y,metadata);expected=stats.contingency.expected_freq(t);sparse=np.any(expected<1) or np.mean(expected<5)>.2;common={'table':t.tolist(),'rowLabels':ls,'columnLabels':cs,'expected':expected.tolist(),'assumptions':[f'Minimum expected count {expected.min():.2f}; {100*np.mean(expected<5):.1f}% of expected counts below five.']}
    if model=='cmh':
        st=spec.get('stratum');require(st and st not in {x,y},'Choose a separate stratum variable.')
        require(t.shape==(2,2),'CMH requires two binary categories for each variable.')
        tables=[]
        for _,g in df.groupby(st):
            tab=pd.crosstab(g[x],g[y]).reindex(index=ls,columns=cs,fill_value=0).to_numpy();require(tab.sum()>=5 and np.all(tab.sum(axis=0)>0) and np.all(tab.sum(axis=1)>0),'Every stratum needs nonempty margins and at least five patients.');tables.append(tab)
        require(len(tables)>=2,'CMH requires at least two strata.')
        fit=StratifiedTable(np.stack(tables,axis=2),shift_zeros=False);r=fit.test_null_odds(correction=False);hom=fit.test_equal_odds(adjust=True);require(np.isfinite(r.pvalue) and np.isfinite(fit.oddsratio_pooled),'CMH is not identifiable.');return result('Cochran–Mantel–Haenszel',float(r.statistic),float(r.pvalue),estimate=float(fit.oddsratio_pooled),confidence=list(fit.oddsratio_pooled_confint()),effect='Common odds ratio',homogeneity={'p':float(hom.pvalue),'method':'Breslow–Day with Tarone adjustment'},strata=len(tables),**common)
    if model=='fisher':
        require(t.shape==(2,2),'Fisher exact test is restricted to 2 by 2 tables; choose the Monte Carlo method for larger tables.')
        r=stats.fisher_exact(t,alternative='two-sided');out=result('Fisher exact test (two-sided)',p=float(r.pvalue),estimate=float(r.statistic),effect='Sample odds ratio',**common)
        if np.all(t>0):out['confidence']=list(Table2x2(t,shift_zeros=False).oddsratio_confint());out['confidenceMethod']='Log-Wald interval, not an exact conditional interval.'
        return out
    stat,p,dof,_=stats.chi2_contingency(t,correction=False,lambda_='log-likelihood' if model=='gtest' else None)
    if model=='ffh':
        require(df.shape[0]<=30000,'Monte Carlo analysis is limited to 30,000 independent patients in this browser.')
        sims=stats.random_table.rvs(t.sum(axis=1),t.sum(axis=0),size=B,random_state=SEED);sim_stat=((sims-expected)**2/expected).sum(axis=(1,2));extreme=int(np.sum(sim_stat>=stat-1e-10));p=(extreme+1)/(B+1);return result('Fixed-margin Monte Carlo Pearson independence test (larger-table alternative)',float(stat),float(p),resampling={'seed':SEED,'replicates':B,'pMonteCarloSE':math.sqrt(p*(1-p)/(B+1)),'pFormula':'(extreme + 1) / (replicates + 1)'},**common)
    require(not sparse,'Sparse contingency table: asymptotic inference is disabled. Choose Fisher exact (2 by 2) or the fixed-margin Monte Carlo alternative.')
    effect=math.sqrt(float(stat)/(len(df)*min(t.shape[0]-1,t.shape[1]-1)))
    if model=='phi':require(t.shape==(2,2),'Phi requires a 2 by 2 table.');effect=float(np.linalg.det(t)/np.sqrt(np.prod(t.sum(axis=0))*np.prod(t.sum(axis=1))))
    require(model in {'chi2','gtest','cramer','phi'},'Unrecognized model.')
    return result({'chi2':'Pearson chi-square (without continuity correction)','gtest':'Likelihood-ratio G-test','cramer':'Cramér V with Pearson chi-square inference','phi':'Phi coefficient with Pearson chi-square inference'}[model],float(stat),float(p),estimate=effect if model!='gtest' else None,effect='Phi' if model=='phi' else 'Cramér V' if model!='gtest' else None,df=dof,**common)

def adjust_family(result_obj,method):
    leaves=[]
    def visit(obj):
        if isinstance(obj,dict):
            if obj.get('p') is not None and isinstance(obj['p'],(float,int)) and np.isfinite(obj['p']):leaves.append(obj)
            for k,v in obj.items():
                if k not in {'diagnostic','homogeneity','omnibus'}:visit(v)
        elif isinstance(obj,list):
            for v in obj:visit(v)
    visit(result_obj)
    if leaves:
        adjusted=multipletests([x['p'] for x in leaves],method='holm' if method!='fdr_bh' else 'fdr_bh')[1]
        for obj,p in zip(leaves,adjusted):obj['adjustedP']=float(p)
    return len(leaves)

def analyse(payload):
    spec=payload['spec'];model=spec['model'];require(model not in UNSUPPORTED,'This model has no validated implementation in this runtime.')
    outcome=spec['outcome'];predictors=spec.get('predictors',[]);metadata={v['key']:v for v in payload['variables']};keys=list(dict.fromkeys([outcome]+predictors+([spec['stratum']] if spec.get('stratum') else [])))
    require(all(k in metadata for k in keys),'Variables are not in the schema-derived catalog.')
    require(len(set(predictors))==len(predictors) and outcome not in predictors,'Select distinct predictor variables, separate from the outcome.')
    if model not in REGRESSION|{'mca','loglinear'}:require(len(predictors)==(0 if model in PAIRED else 1),'This model needs exactly one predictor (none for paired tests).')
    df=pd.DataFrame(payload['rows']);require(len(df)>0,'No recorded entries match these filters.')
    require(set(keys+['patient','date']).issubset(df.columns),'Missing columns in analysis data.')
    require(not df.duplicated(['patient','date']).any(),'Duplicate patient-date rows are not valid observational units.')
    repeated=model in PAIRED or model.startswith('gee')
    require(repeated or not df.patient.duplicated().any(),'Repeated observations cannot be treated as independent patients.')
    require(not repeated or spec.get('unit')=='daily','Repeated analysis requires daily patient-level units.')
    before=len(df);missing_by={metadata[k]['label']:int(df[k].isna().sum()) for k in keys};df=df.dropna(subset=keys).copy();require(len(df)>=5,'Fewer than five complete observations remain after excluding missing values.')
    excluded_missing=before-len(df);unmatched=0;outside_dates=0
    if model in PAIRED:
        dates=sorted(set(spec.get('dates',[])));require(len(dates)>=2,'Select at least two assessment dates.')
        outside_dates=int((~df.date.isin(dates)).sum());df=df[df.date.isin(dates)].copy();pivot=df.pivot(index='patient',columns='date',values=outcome).reindex(columns=dates);matched=set(pivot.dropna().index);unmatched=int(df.patient.nunique()-len(matched));df=df[df.patient.isin(matched)].copy();require(len(matched)>=5,'Fewer than five complete matched patients on the selected dates.')
    require(all(df[k].nunique()>1 for k in keys if k!=spec.get('stratum')),'At least one selected variable has no category variation.')
    require(len(df)<=50000,'This in-browser assessment supports at most 50,000 observations per run.')
    if model=='ca':require(len(df)>=30,'Trend inference requires at least thirty independent patients here.')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        if spec.get('stratum') and model!='cmh':
            require(model not in PAIRED,'Stratified paired analysis is not supported; use explicit cohort filters.')
            st=spec['stratum'];require(st not in [outcome]+predictors,'The stratification variable must be separate from model variables.')
            require(df[st].nunique()<=12,'Too many strata; select a narrower disease cohort.')
            pieces=[]
            for level,g in df.groupby(st):
                try:
                    require(g.patient.nunique()>=5,'Fewer than five patients in stratum.');r=run_test(g,{**spec,'stratum':None},metadata);r.update(stratum=str(level),patients=int(g.patient.nunique()),observations=len(g));pieces.append(r)
                except (EligibilityError,ValueError,np.linalg.LinAlgError) as e:pieces.append({'stratum':str(level),'status':'Insufficient data','reason':str(e)})
            require(any('method' in p for p in pieces),'No stratum meets this model’s eligibility requirements.')
            answer=result('Stratified assessment',strata=pieces)
        else:answer=run_test(df,spec,metadata)
        warning_text=list(dict.fromkeys(str(w.message) for w in caught))
        if model=='loglinear':warning_text=[t for t in warning_text if 'separation' not in t.lower() and 'divide by zero' not in t.lower()]
        require(model not in REGRESSION or not any('separation' in t.lower() for t in warning_text),'Separation detected. Model estimates are not reliable and have been withheld.')
    if predictors and model not in PAIRED and not spec.get('stratum'):
        group='gender' if 'gender' in predictors else predictors[0]
        if metadata[group]['type']!='numeric' and df[group].nunique()<=12 and df[outcome].nunique()<=20:
            t,gl,ol=contingency(df,group,outcome,metadata)
            answer['outcomeByGroup']={'table':t.tolist(),'rowLabels':gl,'columnLabels':ol,'groupLabel':metadata[group]['label']}
            answer['cohortDistributions']=[{'groupLabel':metadata[group]['label'],'group':str(level),'distributions':describe(g,[k for k in keys if k!=group],metadata)} for level,g in df.groupby(group)]
    if answer.get('p') is not None:require(np.isfinite(answer['p']),'No finite p-value could be calculated.')
    family=adjust_family(answer,spec.get('correction','holm'))
    answer.update(schemaVersion=1,dataDigest=hashlib.sha256(json.dumps(payload['rows'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),analysisDate=datetime.now(timezone.utc).isoformat(),model=model,question=spec.get('question') or metadata[outcome]['label']+(' in relation to '+', '.join(metadata[k]['label'] for k in predictors) if predictors else ' across selected assessment dates'),variables=[{k:v for k,v in metadata[key].items() if k in {'key','label','type','order'}} for key in keys],specification=spec,patients=int(df.patient.nunique()),observations=len(df),excludedMissing=excluded_missing,excludedUnmatchedPatients=unmatched,excludedOutsideSelectedDates=outside_dates,missingByVariable=missing_by,audit=payload['audit'],descriptive=describe(df,keys,metadata),software={'Python':__import__('sys').version.split()[0],'SciPy':scipy.__version__,'statsmodels':statsmodels.__version__,'NumPy':np.__version__,'pandas':pd.__version__,'engine':'Pain Gauge clinical assessment 1.0'},correction={'method':spec.get('correction','holm'),'familySize':family,'scope':'P-values in this run, including selected model coefficients, post-hoc comparisons and strata; diagnostics excluded. Not a correction across separate runs.'},warnings=warning_text[:12],limitations=['Exploratory associations from observational, voluntarily entered records; no causal or treatment-effect conclusion.','Complete-case analysis; missing and unchecked fields are not assumed to be negative responses. Selection and reporting bias are possible.','Entry snapshots are used without backfilling from the current profile. Latest within-cohort date is chosen before excluding incomplete model rows.','Nominal and ordinal predictors use reference-category dummy coding in regression; numeric category codes are not quantitative predictors.','Confidence intervals are unadjusted 95% intervals where available; multiplicity-adjusted p-values use the selected family.'] )
    # Results exclude patient-level rows, free-text notes, email, name and patient ID.
    if answer.get('adjustedP') is not None:answer['interpretation']='Evidence of an association under this model after the selected within-run correction.' if answer['adjustedP']<.05 else 'This analysis does not establish an association at the 0.05 threshold; absence of evidence is not evidence of no association.'
    else:answer['interpretation']='Review estimates, uncertainty and eligibility checks. Exploratory patterns do not establish clinical effects.'
    return safe(answer)

def main_json(payload_json):
    try:return json.dumps({'ok':True,'result':analyse(json.loads(payload_json))},allow_nan=False)
    except Exception as e:return json.dumps({'ok':False,'error':str(e),'type':type(e).__name__})

# Shared aggregate export contract. Suppress values for counts below five and
# complementary cells in the same count table, not merely the visible small cell.
def report_rows(r):
    rows=[['Pain Gauge · Statistical Assessment'],['Analysis date',r['analysisDate']],['Method',r['method']],['Research question',r['question']],['Patients',r['patients']],['Observations',r['observations']],['Excluded missing',r['excludedMissing']],['Filters',json.dumps(r['specification'].get('filters',{}),ensure_ascii=False)],['Model specification',json.dumps({k:v for k,v in r['specification'].items() if k!='filters'},ensure_ascii=False)],['Software',json.dumps(r['software'])],['Multiplicity',json.dumps(r['correction'])]]
    for variable in r.get('variables',[]):rows.append(['Variable',variable['label'],variable['type'],json.dumps(variable.get('order'),ensure_ascii=False)])
    def walk(obj,prefix='Result'):
        for k,v in obj.items():
            if k in {'specification','variables','audit','descriptive','matrix','categories','software','limitations','warnings','analysisDate','question','method','patients','observations','excludedMissing','correction','schemaVersion','cohortDistributions'}:continue
            if k in {'table','expected'}:
                counts=np.array(obj.get('table',[]));hide=counts.size and np.any((counts>0)&(counts<5));rows.append([prefix+' '+k,'Suppressed: small-cell disclosure control' if hide else json.dumps(v,ensure_ascii=False)])
            elif isinstance(v,dict):walk(v,prefix+' '+k)
            elif isinstance(v,list) and v and isinstance(v[0],dict):
                if any(isinstance(item.get('n'),(int,float)) and 0<item['n']<5 for item in v):
                    rows.append([prefix+' '+k,'Suppressed: small-cell disclosure control']);continue
                for i,item in enumerate(v):walk(item,prefix+' '+k+' '+str(i+1))
            else:rows.append([prefix+' '+k,json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v])
    walk(r)
    for d in r.get('descriptive',[]):
        hide=any(0<l['n']<5 for l in d['levels']);rows.append(['Distribution',d['variable']])
        if hide:rows.append(['Counts','Suppressed: small-cell disclosure control'])
        else:
            for l in d['levels']:rows.append([l['category'],l['n'],round(l['percent'],2)])
    for k,v in r['missingByVariable'].items():rows.append(['Missing '+k,'<5' if 0<v<5 else v])
    for text in r.get('limitations',[])+r.get('warnings',[]):rows.append(['Limitation',text])
    rows.append(['Privacy','Aggregate export only. No names, account emails, patient IDs, notes or record-level rows. Small count tables are suppressed when any positive count is below five.'])
    return rows

def export_file(result_json,kind):
    import base64
    r=json.loads(result_json);rows=report_rows(r)
    if kind=='csv':
        import csv
        stream=io.StringIO(newline='');w=csv.writer(stream)
        for row in rows:w.writerow([("'"+str(v)) if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in row])
        data=('\ufeff'+stream.getvalue()).encode('utf-8')
    elif kind=='xlsx':
        # Standards-based Open XML workbook, all user text stored as inline strings.
        from xml.sax.saxutils import escape
        import re
        def xml_text(value):return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value)))
        def col(n):
            s=''
            while n:n,k=divmod(n-1,26);s=chr(65+k)+s
            return s
        cells=[]
        for i,row in enumerate(rows,1):
            cs=[]
            for j,v in enumerate(row,1):
                ref=col(j)+str(i)
                if isinstance(v,(int,float)) and not isinstance(v,bool):cs.append(f'<c r="{ref}"><v>{v}</v></c>')
                else:cs.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{xml_text(v)}</t></is></c>')
            cells.append('<row r="'+str(i)+'">'+''.join(cs)+'</row>')
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
            z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Statistical report" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols><col min="1" max="1" width="48" customWidth="1"/><col min="2" max="3" width="80" customWidth="1"/></cols><sheetData>'+''.join(cells)+'</sheetData></worksheet>')
        data=buf.getvalue()
    elif kind=='pdf':
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        buf=io.BytesIO();lines=[]
        for row in rows:
            lines+=textwrap.wrap(' · '.join(str(v) for v in row),width=100,break_long_words=True) or ['']
            lines.append('')
        with PdfPages(buf,metadata={'Title':'Pain Gauge statistical assessment','Author':'Pain Gauge','Subject':'Aggregate clinical statistical report'}) as pdf:
            for page,start in enumerate(range(0,len(lines),49),1):
                fig=plt.figure(figsize=(8.27,11.69));fig.patch.set_facecolor('white');fig.text(.08,.96,'PAIN GAUGE  |  STATISTICAL ASSESSMENT',size=11,weight='bold',color='#164c7e');fig.text(.08,.92,'\n'.join(lines[start:start+49]),size=8,linespacing=1.5,va='top');fig.text(.08,.035,f'Exploratory assessment · Page {page}',size=8,color='#526575');pdf.savefig(fig);plt.close(fig)
            if r.get('estimates'):
                estimates=r['estimates'];fig,ax=plt.subplots(figsize=(8.27,max(4,len(estimates)*.3+1)))
                for i,e in enumerate(estimates):ax.errorbar(e['estimate'],i,xerr=[[e['estimate']-e['low']],[e['high']-e['estimate']]],fmt='o',color='#176eae')
                ax.set_yticks(range(len(estimates)),[e['term'] for e in estimates],fontsize=8);ax.set_xscale('log');ax.axvline(1,color='#8297aa',ls='--');ax.set_title('Adjusted estimates with unadjusted 95% confidence intervals');fig.tight_layout();pdf.savefig(fig);plt.close(fig)
        data=buf.getvalue()
    else:raise ValueError('Unsupported export format.')
    return base64.b64encode(data).decode('ascii')
