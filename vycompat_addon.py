"""Templates for the blank Vehicle Years Compatibility Tool addon.

The GUI creates this mod when no compatibility addon is installed and the user
explicitly asks for one.  The scaffold is deliberately neutral: it contains the
runtime hooks needed by Vehicle Years, but no community-specific year entries,
author details or mod lists.
"""

from __future__ import annotations

import struct
import zlib

import vycompat_icons

ADDON_TITLE = "Vehicle Years Compatibility Tool"
ADDON_AUTHOR = "Vehicle Years Compatibility Tool contributors"
ADDON_ICON_NAME = "icon.png"

ADDON_DESCRIPTION = """Compatibility year data for Farming Simulator 25 mods and base game vehicles.
This addon only fills gaps: a vehicle's own year and the Vehicle Years database
take precedence.

Supported mods:

Supported mods with per-vehicle years:

Supported base game vehicles:"""

BLANK_MODDESC = f"""<?xml version="1.0" encoding="utf-8" standalone="no" ?>
<modDesc descVersion="104">
    <author>{ADDON_AUTHOR}</author>
    <version>1.0.0.0</version>
    <iconFilename>{ADDON_ICON_NAME}</iconFilename>
    <title>
        <en>{ADDON_TITLE}</en>
    </title>
    <description>
        <en>
            <![CDATA[
{ADDON_DESCRIPTION}
            ]]>
        </en>
    </description>
    <dependencies>
        <dependency>FS25_Vehicle_Years</dependency>
    </dependencies>
    <extraSourceFiles>
        <sourceFile filename="vehicle_years_addon.lua"/>
    </extraSourceFiles>
    <multiplayer supported="true"/>
</modDesc>
"""


def _png_chunk(kind, data):
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def default_icon_png():
    """Return the bundled main icon, with the generated icon as fallback."""
    data = vycompat_icons.main_icon_bytes()
    return data if data is not None else make_icon_png()


def make_icon_png(size=256):
    """Return a simple original 256x256 PNG icon for the blank addon."""
    background = (23, 26, 23)
    panel = (34, 39, 34)
    green = (120, 168, 59)
    margin = max(8, size // 24)
    cx = size // 2
    arm_top = int(size * 0.24)
    arm_bottom = int(size * 0.49)
    arm_reach = int(size * 0.21)
    half_thick = max(5, size // 30)
    stem_bottom = int(size * 0.77)

    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG filter: None
        for x in range(size):
            if (
                x < margin or x >= size - margin
                or y < margin or y >= size - margin
            ):
                color = green
            else:
                color = panel if (x + y) % 32 else background
                if arm_top <= y <= arm_bottom:
                    progress = (y - arm_top) / max(1, arm_bottom - arm_top)
                    offset = int(arm_reach * (1.0 - progress))
                    if (
                        abs(x - (cx - offset)) <= half_thick
                        or abs(x - (cx + offset)) <= half_thick
                    ):
                        color = green
                if arm_bottom <= y <= stem_bottom and abs(x - cx) <= half_thick:
                    color = green
            rows.extend((color[0], color[1], color[2], 255))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _png_chunk(b"IEND", b"")
    )


BLANK_LUA = """-- Vehicle Years Compatibility Tool
-- Adds year data on top of FS25_Vehicle_Years for mods and base game vehicles
-- that have no entry in the Vehicle Years database.
--
-- Lookup tables (checked in this order):
--   MOD_VEHICLE_YEARS  - single vehicles of a mod (customEnvironment + XML filename)
--   MOD_YEARS          - a whole mod, same year for every vehicle
--   BASE_GAME_YEARS    - base game vehicles (normalized rawXMLFilename)
--
-- Requires FS25_Vehicle_Years (see modDesc.xml dependency). This file is loaded
-- after vehicle_years.lua, so the "year" / "handtool_year" spec types already
-- exist and can be wrapped.

VehicleYearsCompatibility = {}
VehicleYearsCompatibility.wrappedSpecs = {}

local function vyprint(message)
    print("VehicleYearsCompatibility: " .. tostring(message))
end

-- Years for complete mods, matched by storeItem.customEnvironment (= mod folder name)
local MOD_YEARS = {
}

-- Years for individual vehicles inside a mod that ships several different years.
-- Key: customEnvironment .. "/" .. rawXMLFilename without .xml
local MOD_VEHICLE_YEARS = {
}

-- Years for base game vehicles, matched by normalized rawXMLFilename.
-- Key format: base_data_vehicles_brand_model_model (no .xml extension)
local BASE_GAME_YEARS = {
}

---Convert a raw XML filename to the key used by the Vehicle Years data files.
-- $data/vehicles/brand/model/model.xml -> base_data_vehicles_brand_model_model
-- data/vehicles/brand/model/model.xml  -> base_data_vehicles_brand_model_model
local function normalizeXMLKey(rawXMLFilename)
    if rawXMLFilename == nil then
        return nil
    end

    local key = string.gsub(rawXMLFilename, "\\\\", "/")
    key = string.gsub(key, "%.xml$", "")

    if string.sub(key, 1, 5) == "$data" then
        key = "base_data" .. string.sub(key, 6)
    elseif string.sub(key, 1, 4) == "data" then
        key = "base_" .. key
    end

    key = string.gsub(key, "/", "_")
    return key
end

---Convert a mod relative raw XML filename to the key used in MOD_VEHICLE_YEARS.
-- Z2511.xml -> Z2511
local function normalizeVehicleKey(rawXMLFilename)
    if rawXMLFilename == nil then
        return nil
    end

    local key = string.gsub(rawXMLFilename, "\\\\", "/")
    key = string.gsub(key, "^%./", "")
    key = string.gsub(key, "%.xml$", "")
    return key
end

---Find the compatibility year for a store item.
-- @return year (number or nil), source (string or nil)
function VehicleYearsCompatibility:resolveYear(storeItem)
    if storeItem == nil then
        return nil, nil
    end

    local customEnvironment = storeItem.customEnvironment
    if customEnvironment ~= nil then
        -- Mods that ship vehicles with individual years (matched per vehicle XML)
        local vehicleKey = normalizeVehicleKey(storeItem.rawXMLFilename)
        if vehicleKey ~= nil then
            local combinedKey = customEnvironment .. "/" .. vehicleKey
            if MOD_VEHICLE_YEARS[combinedKey] ~= nil then
                return MOD_VEHICLE_YEARS[combinedKey], "mod-vehicle:" .. combinedKey
            end
        end

        -- Mods where every vehicle shares the same year
        if MOD_YEARS[customEnvironment] ~= nil then
            return MOD_YEARS[customEnvironment], "mod:" .. tostring(customEnvironment)
        end
    end

    local key = normalizeXMLKey(storeItem.rawXMLFilename)
    if key ~= nil and BASE_GAME_YEARS[key] ~= nil then
        return BASE_GAME_YEARS[key], "base:" .. key
    end

    return nil, nil
end

local function getPackName(year)
    if year == nil then
        return nil
    end

    if year < 1950 then
        return "VY_PACK_PRE_1950"
    elseif year < 1960 then
        return "VY_PACK_1950S"
    elseif year < 1970 then
        return "VY_PACK_1960S"
    elseif year < 1980 then
        return "VY_PACK_1970S"
    elseif year < 1990 then
        return "VY_PACK_1980S"
    elseif year < 2000 then
        return "VY_PACK_1990S"
    elseif year < 2010 then
        return "VY_PACK_2000S"
    elseif year < 2020 then
        return "VY_PACK_2010S"
    elseif year < 2030 then
        return "VY_PACK_2020S"
    end

    return nil
end

---Store the year on the store item and add it to the matching decade pack.
-- Never overwrites a year that the mod or Vehicle Years already provided.
function VehicleYearsCompatibility:applyYear(storeItem, year, source)
    if storeItem == nil or year == nil then
        return false
    end

    if storeItem.specs == nil and StoreItemUtil ~= nil and StoreItemUtil.loadSpecsFromXML ~= nil then
        StoreItemUtil.loadSpecsFromXML(storeItem)
    end

    if storeItem.specs == nil then
        storeItem.specs = {}
    end

    local applied = false
    if storeItem.specs.year == nil then
        storeItem.specs.year = year
        applied = true
    end

    if not storeItem.vyAddonPacked then
        storeItem.vyAddonPacked = true
        local packName = getPackName(year)
        if packName ~= nil and storeItem.xmlFilename ~= nil and
            g_storeManager ~= nil and g_storeManager.addPackItem ~= nil then
            pcall(function()
                g_storeManager:addPackItem(packName, storeItem.xmlFilename)
            end)
        end
    end

    if applied and not storeItem.vyAddonLogged then
        storeItem.vyAddonLogged = true
        vyprint(string.format("Applied year %d to '%s' (%s)", year, tostring(storeItem.name), tostring(source)))
    end

    return applied
end

local function getSpecType(specName)
    if g_storeManager == nil then
        return nil
    end

    if g_storeManager.getSpecTypeByName ~= nil then
        local specType = g_storeManager:getSpecTypeByName(specName)
        if specType ~= nil then
            return specType
        end
    end

    if g_storeManager.getSpecTypes ~= nil then
        for _, specType in pairs(g_storeManager:getSpecTypes()) do
            if specType.name == specName then
                return specType
            end
        end
    end

    return nil
end

---Wrap the lazy "get value" function of a Vehicle Years spec type.
-- Vehicle Years registers its loadYear() as the spec getter, which is called
-- by the shop whenever the year of an item is needed. Wrapping it guarantees
-- our years are applied even if store items were not loaded yet on map start.
local function wrapSpecType(specName)
    if VehicleYearsCompatibility.wrappedSpecs[specName] then
        return true
    end

    local specType = getSpecType(specName)
    if specType == nil then
        return false
    end

    local original = specType.getValueFunc or specType.getFunc
    if original == nil then
        return false
    end

    local wrapped = function(storeItem, realItem, ...)
        local year = original(storeItem, realItem, ...)

        if year == nil then
            local addonYear, source = VehicleYearsCompatibility:resolveYear(storeItem)
            if addonYear ~= nil then
                VehicleYearsCompatibility:applyYear(storeItem, addonYear, source)
                year = addonYear
            end
        end

        return year
    end

    if specType.getValueFunc ~= nil then
        specType.getValueFunc = wrapped
    else
        specType.getFunc = wrapped
    end

    VehicleYearsCompatibility.wrappedSpecs[specName] = true
    vyprint("Hooked spec getter '" .. specName .. "'")
    return true
end

---Install the lazy getter hooks. Returns the number of hooked spec types.
function VehicleYearsCompatibility:installSpecHooks()
    local installed = 0
    if wrapSpecType("year") then
        installed = installed + 1
    end
    if wrapSpecType("handtool_year") then
        installed = installed + 1
    end
    return installed
end

---Apply years to all currently known store items.
-- Runs on FSBaseMission.onFinishedLoading and after every StoreManager:addItem.
function VehicleYearsCompatibility:applyToStoreItems(verbose)
    if g_storeManager == nil or g_storeManager.getItems == nil then
        return 0
    end

    local total = 0
    local withEnvironment = 0
    local withRawFilename = 0
    local applied = 0

    for _, storeItem in pairs(g_storeManager:getItems()) do
        total = total + 1

        if storeItem.customEnvironment ~= nil then
            withEnvironment = withEnvironment + 1
        end
        if storeItem.rawXMLFilename ~= nil then
            withRawFilename = withRawFilename + 1
        end

        local year, source = self:resolveYear(storeItem)
        if year ~= nil then
            if self:applyYear(storeItem, year, source) then
                applied = applied + 1
            end
        end
    end

    if verbose then
        vyprint(string.format("Store items: %d (customEnvironment: %d, rawXMLFilename: %d)",
            total, withEnvironment, withRawFilename))
        vyprint(string.format("Applied %d year(s) eagerly", applied))
    end

    return applied
end

-- Defined with a dot on purpose: Utils.appendedFunction does not pass "self".
function VehicleYearsCompatibility.onFinishedLoading()
    vyprint("Map finished loading, applying year data...")
    VehicleYearsCompatibility:applyToStoreItems(true)
    -- Vehicle Years may have registered its spec types before/after us
    VehicleYearsCompatibility:installSpecHooks()
end

-- 1) Lazy path: wrap the spec getter used by the shop.
local hookedSpecs = VehicleYearsCompatibility:installSpecHooks()
if hookedSpecs < 2 and StoreManager ~= nil and StoreManager.addSpecType ~= nil then
    -- Vehicle Years was not loaded yet, retry whenever a spec type is registered.
    StoreManager.addSpecType = Utils.appendedFunction(StoreManager.addSpecType, function()
        VehicleYearsCompatibility:installSpecHooks()
    end)
end

-- 2) Eager path: every store item that is added after this file is loaded
--    (this is where base game and mod items are actually registered).
if StoreManager ~= nil and StoreManager.addItem ~= nil then
    StoreManager.addItem = Utils.appendedFunction(StoreManager.addItem, function(_, storeItem)
        if storeItem ~= nil then
            local year, source = VehicleYearsCompatibility:resolveYear(storeItem)
            if year ~= nil then
                VehicleYearsCompatibility:applyYear(storeItem, year, source)
            end
        end
    end)
end

-- 3) Backup path: catch items that already existed when this file was loaded.
FSBaseMission.onFinishedLoading = Utils.appendedFunction(
    FSBaseMission.onFinishedLoading, VehicleYearsCompatibility.onFinishedLoading)

vyprint("Vehicle Years Compatibility Tool loaded")
"""
