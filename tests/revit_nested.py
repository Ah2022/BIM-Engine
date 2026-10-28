#! python3
"""Verify nested family solids and level metadata in real Revit."""
import os
import sys
import json
import uuid
import traceback
ROOT=r'C:\Users\TK56\Downloads\BIMEngine_Phase1_Hybrid'
sys.path.insert(0,os.path.join(ROOT,'BIMEngine.extension','lib'))
report={'status':'running','checks':[]}
try:
    import clr
    clr.AddReference('RevitAPI')
    from Autodesk.Revit import DB
    from System.Collections.Generic import List
    from bimengine_core.revit_bridge import scan_and_save
    run=os.path.join(ROOT,'verification','nested-'+uuid.uuid4().hex[:8]);os.makedirs(run)
    os.environ['BIMENGINE_DB_PATH']=os.path.join(run,'issues.db')
    app=__revit__.Application
    template=r'C:\ProgramData\Autodesk\RVT 2024\Family Templates\English-Imperial\Generic Model.rft'
    def extrusion(family,x):
        points=[DB.XYZ(x,0,0),DB.XYZ(x+2,0,0),DB.XYZ(x+2,2,0),DB.XYZ(x,2,0)]
        curve=DB.CurveArray()
        for i in range(4):curve.Append(DB.Line.CreateBound(points[i],points[(i+1)%4]))
        curves=DB.CurveArrArray();curves.Append(curve)
        sketch=DB.SketchPlane.Create(family,DB.Plane.CreateByNormalAndOrigin(DB.XYZ.BasisZ,DB.XYZ.Zero))
        family.FamilyCreate.NewExtrusion(True,curves,sketch,2)
    inner=app.NewFamilyDocument(template)
    tx=DB.Transaction(inner,'Two solids');tx.Start();extrusion(inner,0);extrusion(inner,10);tx.Commit()
    inner.SaveAs(os.path.join(run,'inner.rfa'))
    middle=app.NewFamilyDocument(template)
    loaded=inner.LoadFamily(middle)
    tx=DB.Transaction(middle,'Nested instance');tx.Start()
    symbol=middle.GetElement(list(loaded.GetFamilySymbolIds())[0]);symbol.Activate()
    middle.FamilyCreate.NewFamilyInstance(DB.XYZ(5,0,0),symbol,DB.Structure.StructuralType.NonStructural)
    tx.Commit();middle.SaveAs(os.path.join(run,'middle.rfa'));inner.Close(False)
    outer=app.NewFamilyDocument(template)
    loaded=middle.LoadFamily(outer)
    tx=DB.Transaction(outer,'Outer nested instance');tx.Start()
    outer.OwnerFamily.FamilyCategory=outer.Settings.Categories.get_Item(DB.BuiltInCategory.OST_StructuralColumns)
    symbol=outer.GetElement(list(loaded.GetFamilySymbolIds())[0]);symbol.Activate()
    outer.FamilyCreate.NewFamilyInstance(DB.XYZ(5,0,0),symbol,DB.Structure.StructuralType.NonStructural)
    tx.Commit();outer.SaveAs(os.path.join(run,'outer.rfa'));middle.Close(False)
    doc=app.NewProjectDocument(DB.UnitSystem.Imperial)
    loaded=outer.LoadFamily(doc)
    tx=DB.Transaction(doc,'Place nested family');tx.Start()
    level=DB.Level.Create(doc,0)
    symbol=doc.GetElement(list(loaded.GetFamilySymbolIds())[0]);symbol.Activate()
    doc.Create.NewFamilyInstance(DB.XYZ(10,0,0),symbol,level,DB.Structure.StructuralType.Column)
    # Nested secondary box is at x=30..32. Target x=31..33 intersects only that box.
    pts=[DB.XYZ(31,0,0),DB.XYZ(33,0,0),DB.XYZ(33,2,0),DB.XYZ(31,2,0)]
    loop=DB.CurveLoop()
    for i in range(4):loop.Append(DB.Line.CreateBound(pts[i],pts[(i+1)%4]))
    loops=List[DB.CurveLoop]();loops.Add(loop)
    solid=DB.GeometryCreationUtilities.CreateExtrusionGeometry(loops,DB.XYZ.BasisZ,2)
    ds=DB.DirectShape.CreateElement(doc,DB.ElementId(DB.BuiltInCategory.OST_StructuralColumns))
    geometry=List[DB.GeometryObject]();geometry.Add(solid);ds.SetShape(geometry)
    tx.Commit();outer.Close(False)
    doc.SaveAs(os.path.join(run,'nested-host.rvt'))
    result=scan_and_save(doc,dict(Categories=['Structural Columns'],IncludeLinkedDocuments=False,
        OctreeMaxObjectsPerNode=4,OctreeMaxDepth=8,CandidateQueryPaddingFeet=.01))
    report['actual_clashes']=len(result['issues']);report['diagnostics']=result['diagnostics']
    report['checks'].append(dict(name='secondary solid through two nested instances',passed=len(result['issues'])==1 and not result['diagnostics']))
    report['checks'].append(dict(name='nested transforms applied once',passed=bool(result['issues']) and abs(result['issues'][0]['location_x']-31.5)<1e-7))
    doc.Close(False)
    report['status']='passed' if all(c['passed'] for c in report['checks']) else 'failed'
except Exception:
    report['status']='failed';report['error']=traceback.format_exc()
finally:
    with open(os.path.join(ROOT,'verification','revit-nested-result.json'),'w') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report,indent=2))
