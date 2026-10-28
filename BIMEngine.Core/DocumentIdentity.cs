using System;
using Autodesk.Revit.DB;

namespace BIMEngine.Core
{
    public static class DocumentIdentity
    {
        public static string Get(Document doc)
        {
            if (doc == null || doc.IsFamilyDocument)
                throw new ArgumentException("Open a Revit project document first.");
            string path = doc.PathName;
            if (doc.IsModelInCloud)
                path = ModelPathUtils.ConvertModelPathToUserVisiblePath(doc.GetCloudModelPath());
            else if (doc.IsWorkshared)
                path = ModelPathUtils.ConvertModelPathToUserVisiblePath(doc.GetWorksharingCentralModelPath());
            return doc.ProjectInformation.UniqueId + "|" + (path ?? "").ToLowerInvariant();
        }
    }
}
