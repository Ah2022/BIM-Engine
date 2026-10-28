#! python3
import os, json, traceback, uuid
ROOT=r'C:\Users\TK56\Downloads\BIMEngine_Phase1_Hybrid'
RUN=os.path.join(ROOT,'verification','preview-probe-'+uuid.uuid4().hex[:8])
os.makedirs(RUN)
report={'run_directory':RUN,'checks':{}}
try:
    import clr
    clr.AddReference('RevitAPI')
    from Autodesk.Revit import DB
    from System.Collections.Generic import List
    doc=__revit__.Application.NewProjectDocument(DB.UnitSystem.Imperial)
    tx=DB.Transaction(doc,'Probe fixture'); tx.Start()
    level=DB.Level.Create(doc,0)
    types=list(DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType))
    plan=DB.ViewPlan.Create(doc,next(t.Id for t in types if t.ViewFamily==DB.ViewFamily.FloorPlan),level.Id)
    v3=DB.View3D.CreateIsometric(doc,next(t.Id for t in types if t.ViewFamily==DB.ViewFamily.ThreeDimensional))
    plan.Name='BIM Preview Probe Plan'
    tx.Commit()
    path=os.path.join(RUN,'probe.rvt'); doc.SaveAs(path); doc.Close(False)
    ui=__revit__.OpenAndActivateDocument(path); doc=ui.Document
    plan=next(v for v in DB.FilteredElementCollector(doc).OfClass(DB.ViewPlan) if v.Name=='BIM Preview Probe Plan')
    v3=next(v for v in DB.FilteredElementCollector(doc).OfClass(DB.View3D) if not v.IsTemplate)
    for v in [plan,v3]:
        before=v.CropBox; active=v.CropBoxActive
        original_section=v3.GetSectionBox() if isinstance(v,DB.View3D) else None
        tx=DB.Transaction(doc,'Temporary view probe'); tx.Start()
        v.EnableTemporaryViewPropertiesMode(v.Id)
        v.IsolateElementsTemporary(List[DB.ElementId]())
        bb=DB.BoundingBoxXYZ(); bb.Min=DB.XYZ(-3,-4,-5); bb.Max=DB.XYZ(6,7,8)
        if isinstance(v,DB.View3D): v.SetSectionBox(bb); v.IsSectionBoxActive=True
        else: v.CropBox=bb; v.CropBoxActive=True
        tx.Commit()
        during_modified=doc.IsModified
        tx=DB.Transaction(doc,'End temporary mode'); tx.Start()
        v.DisableTemporaryViewMode(DB.TemporaryViewMode.TemporaryHideIsolate)
        v.EnableTemporaryViewPropertiesMode(DB.ElementId.InvalidElementId)
        tx.Commit()
        after=v.CropBox
        report['checks'][str(v.ViewType)]={'crop_restored':before.Min.IsAlmostEqualTo(after.Min) and before.Max.IsAlmostEqualTo(after.Max) and active==v.CropBoxActive,
            'section_restored':original_section is None or (original_section.Min.IsAlmostEqualTo(v3.GetSectionBox().Min) and original_section.Max.IsAlmostEqualTo(v3.GetSectionBox().Max)),
            'modified_during':during_modified,'modified_after':doc.IsModified,'empty_isolation_supported':True}
    doc.Save()
    report['status']='passed'
except Exception:
    report['status']='failed'; report['error']=traceback.format_exc()
finally:
    with open(os.path.join(ROOT,'verification','preview-probe.json'),'w') as stream: json.dump(report,stream,indent=2)
