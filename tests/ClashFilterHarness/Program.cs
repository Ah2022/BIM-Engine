using System;
using System.Linq;
using BIMEngine.Core.Dashboard;

class Program
{
    static int checks;
    static void Check(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
        checks++;
    }
    static ClashSideCategories Side(string category, string system = null, string classification = null)
        => new ClashSideCategories(category, system, classification);

    [STAThread]
    static void Main()
    {
        var beam = Side("Structural Framing");
        var waste = Side("Pipes", "PL-Waste", "Sanitary");
        var soil = Side("Pipes", "PL-Soil", "Sanitary");
        var water = Side("Pipes", "CW", "DomesticColdWater");
        var duct = Side("Ducts", "Supply", "SupplyAir");
        var tray = Side("Cable Trays");
        var sanitary = new ClashCategoryInfo(beam, waste);
        var reverse = new ClashCategoryInfo(waste, beam);
        Check(sanitary.PairLabel == "Structure vs Sanitary", "Beam/waste classification");
        Check(reverse.PairLabel == sanitary.PairLabel, "Pair order independence");
        Check(sanitary.Matches("Structure vs Sanitary", "PL-Waste", "group:Structure"), "Focus on B with opposite group");
        Check(reverse.Matches("Structure vs Sanitary", "PL-Waste", "group:Structure"), "Focus on A with opposite group");
        Check(!sanitary.Matches(null, "PL-Waste", "group:Sanitary"), "Do not match focus element as its opponent");
        Check(!sanitary.Matches(null, "PL-Waste", "system:PL-Waste"), "Do not match focus system as its own opponent");
        Check(sanitary.Matches(null, " pl-waste ".Trim(), null), "Case-insensitive exact system match");
        Check(!sanitary.Matches(null, "Waste", null), "No substring system matches");
        Check(!sanitary.Matches("Structure vs HVAC", "PL-Waste", null), "Combined pair and system filter");
        Check(new ClashCategoryInfo(beam, water).PairLabel == "Structure vs Water Supply", "Water classification");
        Check(new ClashCategoryInfo(waste, duct).PairLabel == "Sanitary vs HVAC", "MEP vs MEP");
        Check(new ClashCategoryInfo(beam, tray).PairLabel == "Structure vs Electrical", "Cable tray classification");
        foreach (string classification in new[] { "FireProtectWet", "FireProtectDry", "FireProtectPreaction", "FireProtectOther" })
            Check(Side("Pipes", "FP", classification).Groups.Single() == "Fire Protection", classification);
        Check(Side("Pipes", "CHWS", "HydronicSupply").Groups.Single() == "HVAC", "Hydronic pipes belong to HVAC");
        Check(Side("Pipe Accessories", "PL-Waste", null).Groups.Single() == "Sanitary", "Explicit project alias");
        Check(Side("Pipes", "PL-Waste", "DomesticColdWater").Groups.Single() == "Water Supply", "Classification overrides alias");
        Check(Side("Pipes", "Custom Waste Name", null).Groups.Single() == "Unassigned/Other", "Do not guess from substrings");
        Check(Side("Pipes").Systems.Single() == "Unassigned", "Missing metadata remains visible");
        Check(Side("Unknown", null, null).Groups.Single() == "Unassigned/Other", "Unknown category");
        Check(Side("Pipes", "PL-Waste", "Process").Groups.Single() == "Unassigned/Other", "Unknown explicit classification is not overridden");
        Check(Side("Pipes", "Supply / Return", "HydronicSupply").Systems.Single() == "Supply / Return", "Literal separator in single type name");

        var multiple = Side("Pipes", "Multiple systems: PL-Waste / CW / pl-waste", "Sanitary / DomesticColdWater");
        var multiClash = new ClashCategoryInfo(beam, multiple);
        Check(multiple.Systems.Length == 2, "Deduplicate multiple systems");
        Check(multiClash.Pairs.Length == 2, "Multiple classifications retain both coordination pairs");
        Check(multiClash.Matches("Structure vs Sanitary", "PL-Waste", "group:Structure"), "Multi-system focus waste");
        Check(multiClash.Matches("Structure vs Water Supply", "CW", "group:Structure"), "Multi-system focus water");
        Check(new ClashCategoryInfo(multiple, multiple).Targets("PL-Waste").Distinct(StringComparer.OrdinalIgnoreCase).Count()
            == new ClashCategoryInfo(multiple, multiple).Targets("PL-Waste").Length, "Opponent choices deduplicate");
        var same = new ClashCategoryInfo(waste, waste);
        Check(same.Matches(null, "PL-Waste", "system:PL-Waste"), "Same system clash is included");
        var otherSanitary = new ClashCategoryInfo(waste, soil);
        Check(otherSanitary.Matches("Sanitary vs Sanitary", "PL-Waste", "system:PL-Soil"), "Exact opponent system");
        Check(!otherSanitary.Matches(null, "PL-Waste", "system:PL-Waste"), "Different sanitary systems stay distinct");
        var clashes = new[] { sanitary, reverse, new ClashCategoryInfo(waste, duct), new ClashCategoryInfo(waste, tray), same, otherSanitary, new ClashCategoryInfo(water, duct) };
        Check(clashes.Count(x => x.Matches(null, "PL-Waste", null)) == 6, "Focus across all opponents, once per row");
        Check(clashes.Count(x => x.Matches(null, "PL-Waste", "group:Structure")) == 2, "Opposite group across orientations");
        Check(sanitary.Targets("PL-Waste").Contains("group:Structure") && !sanitary.Targets("PL-Waste").Contains("group:Sanitary"), "Available against choices use opposite side");
        Check(sanitary.Targets(null).Length == 0, "Against has no choices without focus");
        Console.WriteLine("PASS: " + checks + " clash classification and filtering checks.");
        DashboardPage.RunFilterChecks();
    }
}
