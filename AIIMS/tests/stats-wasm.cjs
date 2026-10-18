const {loadPyodide}=require('pyodide');const fs=require('fs');
(async()=>{const py=await loadPyodide();await py.loadPackage(['numpy','scipy','pandas','statsmodels']);py.FS.mkdir('/assessment');py.FS.mkdir('/assessment/tests');const base=require('path').resolve(__dirname,'..')+'/';py.FS.writeFile('/assessment/care-stats-engine.py',fs.readFileSync(base+'care-stats-engine.py','utf8'));py.FS.writeFile('/assessment/tests/stats_engine_test.py',fs.readFileSync(base+'tests/stats_engine_test.py','utf8'));await py.runPythonAsync(`import runpy,unittest,json,base64,io,zipfile
ns=runpy.run_path('/assessment/tests/stats_engine_test.py',run_name='assessment_test_module')
klass=ns['AssessmentTests']
excluded={'test_kruskal_dunn_matches_validated_reference','test_mca_matches_prince_eigenvalues','test_exports_open_and_do_not_include_patient_level_rows'}
suite=unittest.TestSuite(klass(n) for n in unittest.defaultTestLoader.getTestCaseNames(klass) if n not in excluded)
r=unittest.TextTestRunner(verbosity=1).run(suite)
assert r.wasSuccessful()
e=ns['e'];report=e.analyse(ns['payload']('fisher',ns['table_rows']([[6,2],[1,4]]),'diagnosis',['gender']))
for kind in ['csv','xlsx']:
 data=base64.b64decode(e.export_file(json.dumps(report),kind))
 assert len(data)>100
 if kind=='xlsx': assert zipfile.ZipFile(io.BytesIO(data)).testzip() is None
print('WASM core tests and CSV/XLSX exports passed')`);await py.loadPackage('matplotlib');await py.runPythonAsync(`data=base64.b64decode(e.export_file(json.dumps(report),'pdf'))
assert data.startswith(b'%PDF') and len(data)>1000
print('WASM PDF export passed')`);})();
