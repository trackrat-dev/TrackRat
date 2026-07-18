import Foundation
import CoreLocation

extension Stations {
    // Station coordinates for mapping - synced with backend_v2/src/trackrat/config/stations.py
    static let stationCoordinates: [String: CLLocationCoordinate2D] = [
        // Core NJ Transit/Amtrak stations - Updated GPS coordinates
        "NY": CLLocationCoordinate2D(latitude: 40.750046, longitude: -73.992358),   // New York Penn Station - Updated GPS
        "NP": CLLocationCoordinate2D(latitude: 40.734221, longitude: -74.164554),   // Newark Penn Station - Updated GPS
        "TR": CLLocationCoordinate2D(latitude: 40.218515, longitude: -74.753926), // Trenton Transit Center - Updated GPS
        "HL": CLLocationCoordinate2D(latitude: 40.255309, longitude: -74.70412),   // Hamilton
        "PJ": CLLocationCoordinate2D(latitude: 40.316316, longitude: -74.623753),   // Princeton Junction - Updated GPS
        "MP": CLLocationCoordinate2D(latitude: 40.56864, longitude: -74.329394),   // Metropark - Updated GPS
        "NB": CLLocationCoordinate2D(latitude: 40.497278, longitude: -74.445751),   // New Brunswick
        "SE": CLLocationCoordinate2D(latitude: 40.761188, longitude: -74.075821),   // Secaucus Junction - Updated GPS
        "PH": CLLocationCoordinate2D(latitude: 39.956565, longitude: -75.182327),   // Philadelphia 30th Street Station - Updated GPS
        "WI": CLLocationCoordinate2D(latitude: 39.7369, longitude: -75.5522),   // Wilmington - Updated GPS
        "BA": CLLocationCoordinate2D(latitude: 39.1896, longitude: -76.6934),   // BWI Airport Rail Station - Updated GPS
        "BL": CLLocationCoordinate2D(latitude: 39.3081, longitude: -76.6175),   // Baltimore Penn Station - Updated GPS
        "WS": CLLocationCoordinate2D(latitude: 38.8973, longitude: -77.0064),   // Washington Union Station - Updated GPS
        "BOS": CLLocationCoordinate2D(latitude: 42.3520, longitude: -71.0552),  // Boston South Station - Updated GPS
        "BBY": CLLocationCoordinate2D(latitude: 42.3473, longitude: -71.0764),  // Boston Back Bay - Updated GPS
        
        // Additional Amtrak stations with GPS coordinates
        "BRP": CLLocationCoordinate2D(latitude: 41.1767, longitude: -73.1874),  // Bridgeport, CT
        "HFD": CLLocationCoordinate2D(latitude: 41.7678, longitude: -72.6821),  // Hartford, CT
        "MDN": CLLocationCoordinate2D(latitude: 41.5390, longitude: -72.8012),  // Meriden, CT
        "NHV": CLLocationCoordinate2D(latitude: 41.2987, longitude: -72.9259),  // New Haven, CT
        "NLC": CLLocationCoordinate2D(latitude: 41.3543, longitude: -72.0939),  // New London, CT
        "OSB": CLLocationCoordinate2D(latitude: 41.3005, longitude: -72.3760),  // Old Saybrook, CT
        "STM": CLLocationCoordinate2D(latitude: 41.0462, longitude: -73.5427),  // Stamford, CT
        "WFD": CLLocationCoordinate2D(latitude: 41.4571, longitude: -72.8254),  // Wallingford, CT
        "WNL": CLLocationCoordinate2D(latitude: 41.9272, longitude: -72.6286),  // Windsor Locks, CT
        "ABE": CLLocationCoordinate2D(latitude: 39.5095, longitude: -76.1630),  // Aberdeen, MD
        "NCR": CLLocationCoordinate2D(latitude: 38.9533, longitude: -76.8644),  // New Carrollton, MD
        "SPG": CLLocationCoordinate2D(latitude: 42.1060, longitude: -72.5936),  // Springfield, MA
        "CLA": CLLocationCoordinate2D(latitude: 43.3688, longitude: -72.3793),  // Claremont, NH
        "DOV": CLLocationCoordinate2D(latitude: 43.1979, longitude: -70.8737),  // Dover, NH
        "DHM": CLLocationCoordinate2D(latitude: 43.1340, longitude: -70.9267),  // Durham-UNH, NH
        "EXR": CLLocationCoordinate2D(latitude: 42.9809, longitude: -70.9478),  // Exeter, NH
        "HAR": CLLocationCoordinate2D(latitude: 40.2616, longitude: -76.8782),  // Harrisburg, PA
        "LNC": CLLocationCoordinate2D(latitude: 40.0538, longitude: -76.3076),  // Lancaster, PA
        "PAO": CLLocationCoordinate2D(latitude: 40.0423, longitude: -75.4767),  // Paoli, PA (Keystone)
        "EXT": CLLocationCoordinate2D(latitude: 40.0131, longitude: -75.6233),  // Exton, PA (Keystone)
        "DOW": CLLocationCoordinate2D(latitude: 40.0003, longitude: -75.7042),  // Downingtown, PA (Keystone)
        "COT": CLLocationCoordinate2D(latitude: 39.9823, longitude: -75.8233),  // Coatesville, PA (Keystone)

        "MJY": CLLocationCoordinate2D(latitude: 40.1071, longitude: -76.5033),  // Mount Joy, PA (Keystone)
        "ELT": CLLocationCoordinate2D(latitude: 40.1524, longitude: -76.5258),  // Elizabethtown, PA (Keystone)
        "MIDPA": CLLocationCoordinate2D(latitude: 40.1996, longitude: -76.7322),  // Middletown, PA (Keystone)
        "KIN": CLLocationCoordinate2D(latitude: 41.4885, longitude: -71.5204),  // Kingston, RI
        "PVD": CLLocationCoordinate2D(latitude: 41.8256, longitude: -71.4160),  // Providence, RI
        "WLY": CLLocationCoordinate2D(latitude: 41.3770, longitude: -71.8307),  // Westerly, RI
        "ALX": CLLocationCoordinate2D(latitude: 38.8062, longitude: -77.0626),  // Alexandria, VA
        "CVS": CLLocationCoordinate2D(latitude: 38.0320, longitude: -78.4921),  // Charlottesville, VA
        "LOR": CLLocationCoordinate2D(latitude: 38.7060, longitude: -77.2214),  // Lorton, VA
        "MSS": CLLocationCoordinate2D(latitude: 38.7511, longitude: -77.4752),  // Manassas, VA
        "NFK": CLLocationCoordinate2D(latitude: 36.8583, longitude: -76.2876),  // Norfolk, VA
        "RVR": CLLocationCoordinate2D(latitude: 37.61741, longitude: -77.49755),  // Richmond Staples Mill Road, VA
        "RVM": CLLocationCoordinate2D(latitude: 37.6143, longitude: -77.4966),  // Richmond Main Street, VA
        "RNK": CLLocationCoordinate2D(latitude: 37.3077, longitude: -79.9803),  // Roanoke, VA
        "PF": CLLocationCoordinate2D(latitude: 40.618425, longitude: -74.420163),   // Plainfield (corrected code from PL to PF)
        "LB": CLLocationCoordinate2D(latitude: 40.297145, longitude: -73.988331),   // Long Branch
        "JA": CLLocationCoordinate2D(latitude: 40.476912, longitude: -74.467363),   // Jersey Avenue
        "US": CLLocationCoordinate2D(latitude: 40.683663, longitude: -74.238605),   // Union Station 40.683542211783646, -74.2380068698304
        "AZ": CLLocationCoordinate2D(latitude: 41.030902, longitude: -74.130957),  // Allendale 41.030851610302, -74.13104499027673
        "NA": CLLocationCoordinate2D(latitude: 40.704415, longitude: -74.190717),   // Newark Airport
        "RH": CLLocationCoordinate2D(latitude: 40.606338, longitude: -74.276692),   // Rahway (corrected code from RY to RH)
        "HB": CLLocationCoordinate2D(latitude: 40.734843, longitude: -74.028046), // Hoboken Terminal - Updated GPS
        "RA": CLLocationCoordinate2D(latitude: 40.571005, longitude: -74.634364),   // Raritan  40.5709152209129, -74.63442444281485
        "DN": CLLocationCoordinate2D(latitude: 40.590869, longitude: -74.463043),   // Dunellen
        
        // Additional NJT stations for complete map coverage - Updated GPS
        "ED": CLLocationCoordinate2D(latitude: 40.519148, longitude: -74.410972),   // Edison - Updated GPS
        "MU": CLLocationCoordinate2D(latitude: 40.540736, longitude: -74.360671),   // Metuchen - Updated GPS
        "LI": CLLocationCoordinate2D(latitude: 40.629485, longitude: -74.251772), // Linden - Updated GPS
        "EL": CLLocationCoordinate2D(latitude: 40.265292, longitude: -73.99762), // Elberon - Updated GPS 40.265251400000004, -73.99747922393298
        "EZ": CLLocationCoordinate2D(latitude: 40.667857, longitude: -74.215174), // Elizabeth - Updated GPS
        "NZ": CLLocationCoordinate2D(latitude: 40.680265, longitude: -74.206165),   // North Elizabeth 40.68034147548386, -74.20617290142303
        
        // Additional stations for Raritan Valley and North Jersey Coast Lines
        "BK": CLLocationCoordinate2D(latitude: 40.560929, longitude: -74.530617),   // Bound Brook 40.56125391599582, -74.53021426346963
        "WF": CLLocationCoordinate2D(latitude: 40.649448, longitude: -74.347629),   // Westfield  40.649441391496225, -74.34758901567885
        "AV": CLLocationCoordinate2D(latitude: 40.57762, longitude: -74.27753),   // Avenale 40.57783860099064, -74.27734540034069
        "FW": CLLocationCoordinate2D(latitude: 40.64106, longitude: -74.385003),   // Fanwood  40.64061996072567, -74.38442372790603
        "GW": CLLocationCoordinate2D(latitude: 40.652569, longitude: -74.324794),   // Garwood 40.65255335293603, -74.3250044226773
        "NE": CLLocationCoordinate2D(latitude: 40.629148, longitude: -74.403455),   // Netherwood  40.62921816688348, -74.40322663407635
        "LS": CLLocationCoordinate2D(latitude: 40.326715, longitude: -74.041054),   // Little Silver 40.32654188152892, -74.04054682918307
        "MK": CLLocationCoordinate2D(latitude: 40.3086, longitude: -74.0253),   // Monmouth Park
        "HZ": CLLocationCoordinate2D(latitude: 40.415385, longitude: -74.190393),   // Hazlet 40.41515409414224, -74.19062942410835
        "MI": CLLocationCoordinate2D(latitude: 40.38978, longitude: -74.116131),   // Middletown 40.39082051439342, -74.11679433408341
        "WB": CLLocationCoordinate2D(latitude: 40.55661, longitude: -74.277751),   // Woodbridge
        "RB": CLLocationCoordinate2D(latitude: 40.348284, longitude: -74.074538),   // Red Banka 40.34827140444035, -74.0741512494248
        "PE": CLLocationCoordinate2D(latitude: 40.509398, longitude: -74.273752),   // 40.509372943783205, -74.27381259301205
        "CH": CLLocationCoordinate2D(latitude: 40.484308, longitude: -74.28014),   // South Amboy is mislabelled as Cherry Hill 40.48490168088479, -74.28049932024226
        "AM": CLLocationCoordinate2D(latitude: 40.420161, longitude: -74.223702),   // Aberdeen-Matawan - 40.41977394340468, -74.22209923287113
        
        // Atlantic City Line stations
        "AC": CLLocationCoordinate2D(latitude: 39.363299, longitude: -74.441486),   // Atlantic City Rail Terminal
        "AB": CLLocationCoordinate2D(latitude: 39.424333, longitude: -74.502094),   // Absecon
        "EH": CLLocationCoordinate2D(latitude: 39.526441, longitude: -74.648028),   // Egg Harbor City
        "HN": CLLocationCoordinate2D(latitude: 39.631673, longitude: -74.79946),   // Hammonton
        "AO": CLLocationCoordinate2D(latitude: 39.783547, longitude: -74.907588),   // Atco
        "LW": CLLocationCoordinate2D(latitude: 39.833809, longitude: -75.000314),   // Lindenwold (NJT)
        "CY": CLLocationCoordinate2D(latitude: 39.928447, longitude: -75.041661),   // Cherry Hill
        "PN": CLLocationCoordinate2D(latitude: 39.977769, longitude: -75.061796),   // Pennsauken
        "PR": CLLocationCoordinate2D(latitude: 40.342088, longitude: -74.65887),   // Princeton (shuttle station)

        // Additional NJ Transit stations from STATION_CODES.txt
        "AH": CLLocationCoordinate2D(latitude: 40.237659, longitude: -74.006769),   // Allenhurst
        "AP": CLLocationCoordinate2D(latitude: 40.215359, longitude: -74.014786),   // Asbury Park
        "BB": CLLocationCoordinate2D(latitude: 40.203751, longitude: -74.018891),   // Bradley Beach
        "BS": CLLocationCoordinate2D(latitude: 40.18059, longitude: -74.027301),   // Belmar
        "LA": CLLocationCoordinate2D(latitude: 40.150557, longitude: -74.035481),   // Spring Lake
        "SQ": CLLocationCoordinate2D(latitude: 40.120573, longitude: -74.047688),   // Manasquan
        "PP": CLLocationCoordinate2D(latitude: 40.092718, longitude: -74.048191),   // Point Pleasant Beach 40.092888539579086, -74.04812800404557
        "BH": CLLocationCoordinate2D(latitude: 40.077178, longitude: -74.046183),   // Bay Head 40.077131308867386, -74.04618948520402
        "TS": CLLocationCoordinate2D(latitude: 40.761188, longitude: -74.075821),   // Secaucus Lower Lvl (same location)
        "SC": CLLocationCoordinate2D(latitude: 40.761188, longitude: -74.075821),   // Secaucus Concourse (same location)
        "BW": CLLocationCoordinate2D(latitude: 40.559904, longitude: -74.551741),   // Bridgewater 40.56100944598027, -74.55175688984208
        "SM": CLLocationCoordinate2D(latitude: 40.566075, longitude: -74.61397),   // Somerville 40.56608372758163, -74.61386593713499
        "XC": CLLocationCoordinate2D(latitude: 40.655523, longitude: -74.303226),   // Cranford
        "RL": CLLocationCoordinate2D(latitude: 40.66715, longitude: -74.266323),   // Roselle Park
        "RW": CLLocationCoordinate2D(latitude: 40.980629, longitude: -74.120592),   // Ridgewood
        "RS": CLLocationCoordinate2D(latitude: 40.962206, longitude: -74.133485),   // Glen Rock Main Line
        "UF": CLLocationCoordinate2D(latitude: 40.997369, longitude: -74.113521),   // Hohokus
        "WK": CLLocationCoordinate2D(latitude: 41.012734, longitude: -74.123412),   // Waldwick
        "17": CLLocationCoordinate2D(latitude: 41.07513, longitude: -74.145485),   // Ramsey Route 17
        "RY": CLLocationCoordinate2D(latitude: 41.0571, longitude: -74.1413),   // Ramsey Main St
        "MZ": CLLocationCoordinate2D(latitude: 41.094416, longitude: -74.14662),   // Mahwah
        "SF": CLLocationCoordinate2D(latitude: 41.11354, longitude: -74.153442),   // Suffern
        "XG": CLLocationCoordinate2D(latitude: 41.157138, longitude: -74.191307),   // Sloatsburg
        "TC": CLLocationCoordinate2D(latitude: 41.194208, longitude: -74.18446),   // Tuxedo
        "RM": CLLocationCoordinate2D(latitude: 41.293354, longitude: -74.13987),   // Harriman
        "CB": CLLocationCoordinate2D(latitude: 41.450917, longitude: -74.266554),   // Campbell Hall
        "CW": CLLocationCoordinate2D(latitude: 41.437073, longitude: -74.101871),   // Salisbury Mills-Cornwall 41.436533265171164, -74.10160172915069
        "OS": CLLocationCoordinate2D(latitude: 41.471784, longitude: -74.529212),   // Otisville
        "PO": CLLocationCoordinate2D(latitude: 41.374899, longitude: -74.694622),   // Port Jervis

        // Bergen County Line (Main Line) - New GPS coordinates
        "KG": CLLocationCoordinate2D(latitude: 40.8123, longitude: -74.1246),   // Kingsland
        "LN": CLLocationCoordinate2D(latitude: 40.814165, longitude: -74.122696),   // Lyndhurst
        "DL": CLLocationCoordinate2D(latitude: 40.831369, longitude: -74.131262),   // Delawanna 40.83181871791698, -74.13146171567368
        "PS": CLLocationCoordinate2D(latitude: 40.849411, longitude: -74.133933),   // Passaic 40.84943770250315, -74.13386676844108
        "IF": CLLocationCoordinate2D(latitude: 40.867998, longitude: -74.153206),   // Clifton 40.86791209797451, -74.15326859173946
        "RN": CLLocationCoordinate2D(latitude: 40.914887, longitude: -74.16733),   // Paterson
        "HW": CLLocationCoordinate2D(latitude: 40.942539, longitude: -74.152411),   // Hawthorne 40.94252894598973, -74.15239913775797

        // Bergen County Line (Ridgewood Branch)
        "RF": CLLocationCoordinate2D(latitude: 40.828248, longitude: -74.100563),   // Rutherford
        "WM": CLLocationCoordinate2D(latitude: 40.854979, longitude: -74.096951),   // Wesmont
        "GD": CLLocationCoordinate2D(latitude: 40.866669, longitude: -74.10556),   // Garfield
        "PL": CLLocationCoordinate2D(latitude: 40.884916, longitude: -74.102695),  // Plauderville
        "BF": CLLocationCoordinate2D(latitude: 40.922505, longitude: -74.115236),   // Broadway (Fair Lawn)
        "GK": CLLocationCoordinate2D(latitude: 40.96137, longitude: -74.1293),   // Glen Rock–Boro Hall
        "FZ": CLLocationCoordinate2D(latitude: 40.939914, longitude: -74.121617),   // Radburn Fiar Lawn 40.93964512609563, -74.12154647334052
        
        // Pascack Valley Line
        "WR": CLLocationCoordinate2D(latitude: 40.843974, longitude: -74.078719),   // Wood-Ridge
        "TE": CLLocationCoordinate2D(latitude: 40.864858, longitude: -74.062676),   // Teterboro
        "EX": CLLocationCoordinate2D(latitude: 40.878973, longitude: -74.051893),   // Essex Street
        "AS": CLLocationCoordinate2D(latitude: 40.894458, longitude: -74.043781),   // Anderson Street
        "NH": CLLocationCoordinate2D(latitude: 40.910856, longitude: -74.035044),  // New Bridge Landing
        "RG": CLLocationCoordinate2D(latitude: 40.935146, longitude: -74.02914),   // River Edge
        "OD": CLLocationCoordinate2D(latitude: 40.953478, longitude: -74.029983),   // Oradell
        "EN": CLLocationCoordinate2D(latitude: 40.975036, longitude: -74.027474),   // Emerson
        "HD": CLLocationCoordinate2D(latitude: 41.002414, longitude: -74.041033),   // Hillsdale 41.002418880662276, -74.0409560175139
        "WW": CLLocationCoordinate2D(latitude: 40.990817, longitude: -74.032696),   // Westwood
        "WL": CLLocationCoordinate2D(latitude: 41.021078, longitude: -74.040775),   // Woodcliff Lake
        "PV": CLLocationCoordinate2D(latitude: 41.032305, longitude: -74.036164),   // Park Ridge
        "ZM": CLLocationCoordinate2D(latitude: 41.040879, longitude: -74.029152),   // Montvale
        "PQ": CLLocationCoordinate2D(latitude: 41.058181, longitude: -74.02232),  // Pearl River, NY
        "NN": CLLocationCoordinate2D(latitude: 41.090015, longitude: -74.014794),   // Nanuet, NY
        "SV": CLLocationCoordinate2D(latitude: 41.111978, longitude: -74.043991),   // Spring Valley, NY
        /*
        // Port Jervis Line (from Suffern)
        "SL": CLLocationCoordinate2D(latitude: 41.1568, longitude: -74.1937),   // Sloatsburg, NY
        "TX": CLLocationCoordinate2D(latitude: 41.1970, longitude: -74.1885),   // Tuxedo, NY
        "HR": CLLocationCoordinate2D(latitude: 41.3098, longitude: -74.1526),   // Harriman, NY
        "SM": CLLocationCoordinate2D(latitude: 40.566075, longitude: -74.61397),   // Salisbury Mills–Cornwall, NY
        "MD": CLLocationCoordinate2D(latitude: 41.4459, longitude: -74.4222),   // Middletown, NY
        "OT": CLLocationCoordinate2D(latitude: 41.4783, longitude: -74.5336),   // Otisville, NY
        "PJV": CLLocationCoordinate2D(latitude: 41.3746, longitude: -74.6927),  // Port Jervis, NY
        */
        
        // Morris & Essex Line / Gladstone Branch - Updated GPS
        "MB": CLLocationCoordinate2D(latitude: 40.725622, longitude: -74.303755), // Millburn 40.72567492520069, -74.30369154451178
        "BU": CLLocationCoordinate2D(latitude: 40.765134, longitude: -74.218612), // Brick Church 40.76565601951543, -74.2190988886858
        "EO": CLLocationCoordinate2D(latitude: 40.760977, longitude: -74.210464), // East Orange 40.7608982536601, -74.2107669015754
        "OG": CLLocationCoordinate2D(latitude: 40.771883, longitude: -74.233103), // Orange 40.77189922949034, -74.23311030419556
        "HI": CLLocationCoordinate2D(latitude: 40.766863, longitude: -74.243744), // Highland Avenue 40.76686685018996, -74.24370939011305
        "MT": CLLocationCoordinate2D(latitude: 40.755365, longitude: -74.253024), // Mountain Station 40.75538322553456, -74.25299181567573
        "SO": CLLocationCoordinate2D(latitude: 40.745952, longitude: -74.260538), // South Orange 40.745989173313006, -74.26034504763733
        "MW": CLLocationCoordinate2D(latitude: 40.731149, longitude: -74.275427), // Maplewood 40.73105253148527, -74.27536805310443
        "RT": CLLocationCoordinate2D(latitude: 40.725249, longitude: -74.323754), // Short Hills 40.72518379457189, -74.32377264451166
        "CM": CLLocationCoordinate2D(latitude: 40.740137, longitude: -74.384812), // Chatham 40.740191597353025, -74.38482449543406
        "MA": CLLocationCoordinate2D(latitude: 40.757028, longitude: -74.415105), // Madison 40.75704022512916, -74.41522448684061
        "CN": CLLocationCoordinate2D(latitude: 40.779038, longitude: -74.443435), // Convent Station 40.778934247012046, -74.4433639138298
        "MR": CLLocationCoordinate2D(latitude: 40.797113, longitude: -74.474086), // Morristown 40.797179293283016, -74.47419806965395
        "MX": CLLocationCoordinate2D(latitude: 40.828637, longitude: -74.478197), // Morris Plains 40.82860342578615, -74.47824651382828
        "TB": CLLocationCoordinate2D(latitude: 40.875904, longitude: -74.481915), // Mount Tabor 40.87588239601982, -74.48176730707961
        "ST": CLLocationCoordinate2D(latitude: 40.716549, longitude: -74.357807),   // Summit  40.71666454825247, -74.35768030218206
        "ND": CLLocationCoordinate2D(latitude: 40.747621, longitude: -74.171943),   // Newark Broad Street
        "DV": CLLocationCoordinate2D(latitude: 40.8839, longitude: -74.481513),   // Denville
        "PC": CLLocationCoordinate2D(latitude: 40.708794, longitude: -74.658469),   // Peapack
        "NV": CLLocationCoordinate2D(latitude: 40.712022, longitude: -74.386501),   // New Providence
	"MH": CLLocationCoordinate2D(latitude: 40.695068, longitude: -74.403134),   // Murray Hill
	"BY": CLLocationCoordinate2D(latitude: 40.682345, longitude: -74.442649),   // Berkeley Heights
	"GI": CLLocationCoordinate2D(latitude: 40.678251, longitude: -74.468317),   // Gillette
	"SG": CLLocationCoordinate2D(latitude: 40.674579, longitude: -74.493723),   // Stirling
	"GO": CLLocationCoordinate2D(latitude: 40.673513, longitude: -74.523606),   // Millington
	"LY": CLLocationCoordinate2D(latitude: 40.684844, longitude: -74.54947),   // Lyons
	"BI": CLLocationCoordinate2D(latitude: 40.711378, longitude: -74.55527),   // Basking Ridge
	"BV": CLLocationCoordinate2D(latitude: 40.716845, longitude: -74.571023),   // Bernardsville
	"FH": CLLocationCoordinate2D(latitude: 40.68571, longitude: -74.633734),   // Far Hills
         // Montclair-Boonton Line - Updated GPS
	"WT": CLLocationCoordinate2D(latitude: 40.782743, longitude: -74.198451),   // Watsessing Ave
	"BM": CLLocationCoordinate2D(latitude: 40.792709, longitude: -74.200043),   // Bloomfield
	"GG": CLLocationCoordinate2D(latitude: 40.80059, longitude: -74.204655),   // Glenn Ridge
	"MC": CLLocationCoordinate2D(latitude: 40.808178, longitude: -74.208681),   // Bay Street
	"WA": CLLocationCoordinate2D(latitude: 40.81716518884647, longitude: -74.20955720561183),   // Walnut street
	"WG": CLLocationCoordinate2D(latitude: 40.829514, longitude: -74.206934),   // Watchung
	"UM": CLLocationCoordinate2D(latitude: 40.842004, longitude: -74.209368),   // Upper Montclair
	"MS": CLLocationCoordinate2D(latitude: 40.848715, longitude: -74.205306),   // Mountain Avenue
	"HS": CLLocationCoordinate2D(latitude: 40.857536, longitude: -74.2025), // Montclair Heights
	"UV": CLLocationCoordinate2D(latitude: 40.869782, longitude: -74.197439),   // Montclair State University
	"FA": CLLocationCoordinate2D(latitude: 40.880669, longitude: -74.235372),   // Little Falls
	"GA": CLLocationCoordinate2D(latitude: 40.8847, longitude: -74.2539),   // Great Notch
	"23": CLLocationCoordinate2D(latitude: 40.900254, longitude: -74.256971),   // Wayne Rt 23
	"MV": CLLocationCoordinate2D(latitude: 40.914402, longitude: -74.268158),   // Mountain View
	"LP": CLLocationCoordinate2D(latitude: 40.924138, longitude: -74.301826),   // Lincoln Park
	"TO": CLLocationCoordinate2D(latitude: 40.922809, longitude: -74.343842),   // Towaco
	"DO": CLLocationCoordinate2D(latitude: 40.883415, longitude: -74.555887), // Dover
	"ML": CLLocationCoordinate2D(latitude: 40.885947, longitude: -74.433604),   // Mountain Lakes
	"BN": CLLocationCoordinate2D(latitude: 40.903378, longitude: -74.407736),  // Boonton

	"HV": CLLocationCoordinate2D(latitude: 40.89659, longitude: -74.632731),  // Mount Arlington
	"HP": CLLocationCoordinate2D(latitude: 40.904219, longitude: -74.665697),  // Lake Hopatcong
	"NT": CLLocationCoordinate2D(latitude: 40.897552, longitude: -74.707317),  // Netcong
	"OL": CLLocationCoordinate2D(latitude: 40.907376, longitude: -74.730653),  // Mount Olive
	"HQ": CLLocationCoordinate2D(latitude: 40.851444, longitude: -74.835352),  // Hackettstown
	"GL": CLLocationCoordinate2D(latitude: 40.720284, longitude: -74.666371),  // Gladstone
	"OR": CLLocationCoordinate2D(latitude: 40.59202, longitude: -74.683802),  // North Branch
	"WH": CLLocationCoordinate2D(latitude: 40.615611, longitude: -74.77066),  //  White House
	"ON": CLLocationCoordinate2D(latitude: 40.636903, longitude: -74.835766),  // Lebanon
	"AN": CLLocationCoordinate2D(latitude: 40.645173, longitude: -74.878569),  // Annandale
	"HG": CLLocationCoordinate2D(latitude: 40.666884, longitude: -74.895863),  // High Bridge

        // PATH stations - synced with backend_v2/src/trackrat/config/stations.py
        "PNK": CLLocationCoordinate2D(latitude: 40.7365, longitude: -74.1640),   // Newark PATH
        "PHR": CLLocationCoordinate2D(latitude: 40.7393, longitude: -74.1560),   // Harrison PATH
        "PJS": CLLocationCoordinate2D(latitude: 40.7328, longitude: -74.0630),   // Journal Square
        "PGR": CLLocationCoordinate2D(latitude: 40.7197, longitude: -74.0434),   // Grove Street
        "PEX": CLLocationCoordinate2D(latitude: 40.7167, longitude: -74.0333),   // Exchange Place
        "PNP": CLLocationCoordinate2D(latitude: 40.7265, longitude: -74.0337),   // Newport
        "PHO": CLLocationCoordinate2D(latitude: 40.7348, longitude: -74.0280),   // Hoboken PATH
        "PCH": CLLocationCoordinate2D(latitude: 40.7329, longitude: -74.0067),   // Christopher Street
        "P9S": CLLocationCoordinate2D(latitude: 40.7340, longitude: -73.9997),   // 9th Street
        "P14": CLLocationCoordinate2D(latitude: 40.7376, longitude: -73.9967),   // 14th Street
        "P23": CLLocationCoordinate2D(latitude: 40.7428, longitude: -73.9930),   // 23rd Street
        "P33": CLLocationCoordinate2D(latitude: 40.7487, longitude: -73.9880),   // 33rd Street
        "PWC": CLLocationCoordinate2D(latitude: 40.7118, longitude: -74.0101),   // World Trade Center

        // PATCO Speedline stations - synced with backend_v2/src/trackrat/config/stations.py
        "LND": CLLocationCoordinate2D(latitude: 39.833962, longitude: -75.000664),  // Lindenwold
        "ASD": CLLocationCoordinate2D(latitude: 39.858705, longitude: -75.00921),   // Ashland
        "WCT": CLLocationCoordinate2D(latitude: 39.870263, longitude: -75.011242),  // Woodcrest
        "HDF": CLLocationCoordinate2D(latitude: 39.89764, longitude: -75.037141),   // Haddonfield
        "WMT": CLLocationCoordinate2D(latitude: 39.90706, longitude: -75.046553),   // Westmont
        "CLD": CLLocationCoordinate2D(latitude: 39.91359, longitude: -75.06456),    // Collingswood
        "BWY": CLLocationCoordinate2D(latitude: 39.943135, longitude: -75.120364),  // Broadway PATCO
        "CTH": CLLocationCoordinate2D(latitude: 39.945469, longitude: -75.121242),  // City Hall PATCO
        "FKS": CLLocationCoordinate2D(latitude: 39.955298, longitude: -75.151157),  // Franklin Square
        "EMK": CLLocationCoordinate2D(latitude: 39.950979, longitude: -75.153515),  // 8th and Market
        "NTL": CLLocationCoordinate2D(latitude: 39.947345, longitude: -75.15751),   // 9-10th and Locust
        "TWL": CLLocationCoordinate2D(latitude: 39.947944, longitude: -75.162365),  // 12-13th and Locust
        "FFL": CLLocationCoordinate2D(latitude: 39.948634, longitude: -75.167792),  // 15-16th and Locust

        // Additional Amtrak stations (Southeast/South)
        "ATL": CLLocationCoordinate2D(latitude: 33.7995643615723, longitude: -84.3917846679688),   // Atlanta, GA
        "CHS": CLLocationCoordinate2D(latitude: 32.8755340576172, longitude: -79.9989013671875),   // Charleston, SC
        "CSN": CLLocationCoordinate2D(latitude: 34.6910, longitude: -82.8325),   // Clemson, SC
        "CLT": CLLocationCoordinate2D(latitude: 35.2411460876465, longitude: -80.8236389160156),   // Charlotte, NC
        "DIL": CLLocationCoordinate2D(latitude: 34.418285369873, longitude: -79.3717575073242),    // Dillon, SC
        "DLB": CLLocationCoordinate2D(latitude: 26.4551792144775, longitude: -80.092529296875),    // Delray Beach, FL
        "DLD": CLLocationCoordinate2D(latitude: 29.0168342590332, longitude: -81.3524551391602),   // DeLand, FL
        "DNC": CLLocationCoordinate2D(latitude: 35.9970359802246, longitude: -78.9072265625),     // Durham, NC
        "FLO": CLLocationCoordinate2D(latitude: 34.1988182067871, longitude: -79.7570953369141),   // Florence, SC
        "FTL": CLLocationCoordinate2D(latitude: 26.1196136474609, longitude: -80.1701889038086),   // Fort Lauderdale, FL
        "GAS": CLLocationCoordinate2D(latitude: 35.2683563232422, longitude: -81.1639785766602),   // Gastonia, NC
        "HAM": CLLocationCoordinate2D(latitude: 34.8830718994141, longitude: -79.6984558105469),   // Hamlet, NC
        "HPT": CLLocationCoordinate2D(latitude: 35.9575080871582, longitude: -80.0058364868164),   // High Point, NC
        "JAX": CLLocationCoordinate2D(latitude: 30.3665771484375, longitude: -81.7246017456055),   // Jacksonville, FL
        "KIS": CLLocationCoordinate2D(latitude: 28.293270111084, longitude: -81.4048690795898),    // Kissimmee, FL
        "KTR": CLLocationCoordinate2D(latitude: 33.664379119873, longitude: -79.8290634155273),    // Kingstree, SC
        "LKL": CLLocationCoordinate2D(latitude: 28.04568, longitude: -81.95188),   // Lakeland, FL
        "MIA": CLLocationCoordinate2D(latitude: 25.8498477935791, longitude: -80.2580718994141),   // Miami, FL
        "ORL": CLLocationCoordinate2D(latitude: 28.5256938934326, longitude: -81.3817443847656),   // Orlando, FL
        "PTB": CLLocationCoordinate2D(latitude: 37.2416191101074, longitude: -77.4289703369141),   // Petersburg, VA
        "RGH": CLLocationCoordinate2D(latitude: 35.7795, longitude: -78.6382),                     // Raleigh, NC
        "RMT": CLLocationCoordinate2D(latitude: 35.9382, longitude: -77.7905),                     // Rocky Mount, NC
        "SAL": CLLocationCoordinate2D(latitude: 35.6740, longitude: -80.4842),                     // Salisbury, NC
        "SAV": CLLocationCoordinate2D(latitude: 32.0835, longitude: -81.0998),                     // Savannah, GA
        "SPB": CLLocationCoordinate2D(latitude: 34.9496, longitude: -81.9318),                     // Spartanburg, SC
        "TPA": CLLocationCoordinate2D(latitude: 27.9506, longitude: -82.4572),                     // Tampa, FL
        "WLD": CLLocationCoordinate2D(latitude: 29.7899, longitude: -82.1712),                     // Waldo, FL
        "OCA": CLLocationCoordinate2D(latitude: 29.1871, longitude: -82.1301),                     // Ocala, FL
        "WLN": CLLocationCoordinate2D(latitude: 35.7230682373047, longitude: -77.9082946777344),   // Wilson, NC
        "WPB": CLLocationCoordinate2D(latitude: 26.7153, longitude: -80.0534),                     // West Palm Beach, FL
        "WPK": CLLocationCoordinate2D(latitude: 28.5990, longitude: -81.3392),                     // Winter Park, FL
        "WTH": CLLocationCoordinate2D(latitude: 28.0222, longitude: -81.7323),                     // Winter Haven, FL

        // Missing Southeast stations (added for route topology)
        "SOU": CLLocationCoordinate2D(latitude: 35.1740, longitude: -79.3920),                     // Southern Pines, NC
        "SEL": CLLocationCoordinate2D(latitude: 35.5351, longitude: -78.2836),                     // Selma-Smithfield, NC
        "CAR": CLLocationCoordinate2D(latitude: 35.7830, longitude: -78.7810),                     // Cary, NC
        "GRB": CLLocationCoordinate2D(latitude: 36.0726, longitude: -79.7920),                     // Greensboro, NC
        "TOC": CLLocationCoordinate2D(latitude: 34.5773, longitude: -83.3315),                     // Toccoa, GA
        "GAI": CLLocationCoordinate2D(latitude: 34.2979, longitude: -83.8241),                     // Gainesville, GA
        "JES": CLLocationCoordinate2D(latitude: 31.6036, longitude: -81.8854),                     // Jesup, GA
        "PAL": CLLocationCoordinate2D(latitude: 29.6486, longitude: -81.6376),                     // Palatka, FL
        "SAN": CLLocationCoordinate2D(latitude: 28.8122, longitude: -81.3130),                     // Sanford, FL
        "HLW": CLLocationCoordinate2D(latitude: 26.0112, longitude: -80.1495),                     // Hollywood, FL

        // Nationwide Amtrak stations
        "CHI": CLLocationCoordinate2D(latitude: 41.8787, longitude: -87.6394),  // Chicago Union Station
        "STL": CLLocationCoordinate2D(latitude: 38.6242, longitude: -90.2040),  // St. Louis
        "MKE": CLLocationCoordinate2D(latitude: 43.0345, longitude: -87.9171),  // Milwaukee
        "LAX": CLLocationCoordinate2D(latitude: 34.0562, longitude: -118.2368), // Los Angeles Union Station
        "SEA": CLLocationCoordinate2D(latitude: 47.5984, longitude: -122.3302), // Seattle King Street
        "PDX": CLLocationCoordinate2D(latitude: 45.5287, longitude: -122.6768), // Portland Union Station
        "EMY": CLLocationCoordinate2D(latitude: 37.8405, longitude: -122.2916), // Emeryville
        "SAC": CLLocationCoordinate2D(latitude: 38.5840, longitude: -121.5007), // Sacramento
        "NOL": CLLocationCoordinate2D(latitude: 29.9461, longitude: -90.0783),  // New Orleans
        "SAS": CLLocationCoordinate2D(latitude: 29.4194, longitude: -98.4781),  // San Antonio
        "DEN": CLLocationCoordinate2D(latitude: 39.7530, longitude: -104.9999), // Denver Union Station
        // California / Southwest
        "SBA": CLLocationCoordinate2D(latitude: 34.4137, longitude: -119.6857), // Santa Barbara
        "SLO": CLLocationCoordinate2D(latitude: 35.2730, longitude: -120.6574), // San Luis Obispo
        "SJC": CLLocationCoordinate2D(latitude: 37.3297, longitude: -121.9021), // San Jose
        "OSD": CLLocationCoordinate2D(latitude: 33.1954, longitude: -117.3803), // Oceanside
        "SNA": CLLocationCoordinate2D(latitude: 33.7489, longitude: -117.8664), // Santa Ana
        "FUL": CLLocationCoordinate2D(latitude: 33.8715, longitude: -117.9246), // Fullerton
        "OLT": CLLocationCoordinate2D(latitude: 32.7548, longitude: -117.1976), // San Diego Old Town
        "ABQ": CLLocationCoordinate2D(latitude: 35.0844, longitude: -106.6488), // Albuquerque
        "FLG": CLLocationCoordinate2D(latitude: 35.1981, longitude: -111.6476), // Flagstaff
        "TUS": CLLocationCoordinate2D(latitude: 32.2193, longitude: -110.9643), // Tucson
        "ELP": CLLocationCoordinate2D(latitude: 31.7590, longitude: -106.4890), // El Paso
        "RNO": CLLocationCoordinate2D(latitude: 39.5295, longitude: -119.7773), // Reno
        "TRU": CLLocationCoordinate2D(latitude: 39.3278, longitude: -120.1850), // Truckee
        // Pacific Northwest
        "TAC": CLLocationCoordinate2D(latitude: 47.2420, longitude: -122.4282), // Tacoma
        "EUG": CLLocationCoordinate2D(latitude: 44.0543, longitude: -123.0950), // Eugene
        "SLM": CLLocationCoordinate2D(latitude: 44.9429, longitude: -123.0353), // Salem
        "SLC": CLLocationCoordinate2D(latitude: 40.7774, longitude: -111.9301), // Salt Lake City
        "WFH": CLLocationCoordinate2D(latitude: 48.4106, longitude: -114.3375), // Whitefish
        "GPK": CLLocationCoordinate2D(latitude: 48.4481, longitude: -113.2176), // East Glacier Park
        "HAV": CLLocationCoordinate2D(latitude: 48.5528, longitude: -109.6822), // Havre
        "MSP": CLLocationCoordinate2D(latitude: 44.9464, longitude: -93.0854),  // St. Paul-Minneapolis
        // Texas / South Central
        "DAL": CLLocationCoordinate2D(latitude: 32.7789, longitude: -96.8083),  // Dallas
        "FTW": CLLocationCoordinate2D(latitude: 32.7511, longitude: -97.3340),  // Fort Worth
        "HOS": CLLocationCoordinate2D(latitude: 29.7689, longitude: -95.3597),  // Houston
        "AUS": CLLocationCoordinate2D(latitude: 30.2748, longitude: -97.7268),  // Austin
        "LRK": CLLocationCoordinate2D(latitude: 34.7345, longitude: -92.2740),  // Little Rock
        "MEM": CLLocationCoordinate2D(latitude: 35.1352, longitude: -90.0510),  // Memphis
        // Midwest / Great Lakes
        "KCY": CLLocationCoordinate2D(latitude: 39.0912, longitude: -94.5556),  // Kansas City
        "OKC": CLLocationCoordinate2D(latitude: 35.4728, longitude: -97.5153),  // Oklahoma City
        "OMA": CLLocationCoordinate2D(latitude: 41.2535, longitude: -95.9319),  // Omaha
        "IND": CLLocationCoordinate2D(latitude: 39.7642, longitude: -86.1637),  // Indianapolis
        "CIN": CLLocationCoordinate2D(latitude: 39.1033, longitude: -84.5123),  // Cincinnati
        "CLE": CLLocationCoordinate2D(latitude: 41.5159, longitude: -81.6848),  // Cleveland
        "TOL": CLLocationCoordinate2D(latitude: 41.6529, longitude: -83.5328),  // Toledo
        "DET": CLLocationCoordinate2D(latitude: 42.3289, longitude: -83.0521),  // Detroit
        "GRR": CLLocationCoordinate2D(latitude: 42.9669, longitude: -85.6760),  // Grand Rapids
        "PGH": CLLocationCoordinate2D(latitude: 40.4447, longitude: -79.9923),  // Pittsburgh
        // Northeast extensions
        "ALB": CLLocationCoordinate2D(latitude: 42.6418, longitude: -73.7542),  // Albany-Rensselaer
        "SYR": CLLocationCoordinate2D(latitude: 43.0473, longitude: -76.1440),  // Syracuse
        "ROC": CLLocationCoordinate2D(latitude: 43.1566, longitude: -77.6088),  // Rochester
        "BUF": CLLocationCoordinate2D(latitude: 42.9038, longitude: -78.8636),  // Buffalo Depew
        "MTR": CLLocationCoordinate2D(latitude: 45.5017, longitude: -73.5673),  // Montreal
        "POR": CLLocationCoordinate2D(latitude: 43.6559, longitude: -70.2614),  // Portland ME
        "ESX": CLLocationCoordinate2D(latitude: 44.4881, longitude: -73.1820),  // Essex Junction
        "BTN": CLLocationCoordinate2D(latitude: 44.4759, longitude: -73.2121),  // Burlington VT
        // Virginia / Southeast
        "LYH": CLLocationCoordinate2D(latitude: 37.4083, longitude: -79.1428),  // Lynchburg
        "NPN": CLLocationCoordinate2D(latitude: 36.9814, longitude: -76.4356),  // Newport News
        "WBG": CLLocationCoordinate2D(latitude: 37.2710, longitude: -76.7075),  // Williamsburg
        "CLB": CLLocationCoordinate2D(latitude: 34.0006, longitude: -81.0349),  // Columbia SC
        "BHM": CLLocationCoordinate2D(latitude: 33.5206, longitude: -86.8344),  // Birmingham
        "MOE": CLLocationCoordinate2D(latitude: 30.6959, longitude: -88.0411),  // Mobile

        // California
        "ANA": CLLocationCoordinate2D(latitude: 33.8038, longitude: -117.8773),  // Anaheim
        "ARC": CLLocationCoordinate2D(latitude: 40.8686, longitude: -124.0838),  // Arcata
        "ARN": CLLocationCoordinate2D(latitude: 38.9036, longitude: -121.0832),  // Auburn
        "BAR": CLLocationCoordinate2D(latitude: 34.9048, longitude: -117.0254),  // Barstow
        "BBK": CLLocationCoordinate2D(latitude: 34.1789, longitude: -118.3118),  // Burbank
        "BFD": CLLocationCoordinate2D(latitude: 35.3721, longitude: -119.0082),  // Bakersfield
        "BKY": CLLocationCoordinate2D(latitude: 37.8673, longitude: -122.3007),  // Berkeley
        "BUR": CLLocationCoordinate2D(latitude: 34.1931, longitude: -118.3538),  // Burbank
        "CIC": CLLocationCoordinate2D(latitude: 39.7233, longitude: -121.8459),  // Chico
        "CLM": CLLocationCoordinate2D(latitude: 34.0945, longitude: -117.7169),  // Claremont
        "CML": CLLocationCoordinate2D(latitude: 34.2159, longitude: -119.0341),  // Camarillo
        "COX": CLLocationCoordinate2D(latitude: 39.0992, longitude: -120.9531),  // Colfax
        "CPN": CLLocationCoordinate2D(latitude: 34.3968, longitude: -119.5230),  // Carpinteria
        "CWT": CLLocationCoordinate2D(latitude: 34.2532, longitude: -118.5994),  // Chatsworth
        "DAV": CLLocationCoordinate2D(latitude: 38.5436, longitude: -121.7377),  // Davis
        "DBP": CLLocationCoordinate2D(latitude: 37.7028, longitude: -121.8977),  // Dublin-Pleasanton
        "DUN": CLLocationCoordinate2D(latitude: 41.2111, longitude: -122.2706),  // Dunsmuir
        "ELK": CLLocationCoordinate2D(latitude: 40.8365, longitude: -115.7505),  // Elko
        "FFV": CLLocationCoordinate2D(latitude: 38.2856, longitude: -121.9679),  // Fairfield-Vacaville
        "FMT": CLLocationCoordinate2D(latitude: 37.5591, longitude: -122.0075),  // Fremont
        "FNO": CLLocationCoordinate2D(latitude: 36.7385, longitude: -119.7829),  // Fresno
        "GAC": CLLocationCoordinate2D(latitude: 37.4068, longitude: -121.9670),  // Santa Clara Great America
        "GDL": CLLocationCoordinate2D(latitude: 34.1237, longitude: -118.2589),  // Glendale
        "GLY": CLLocationCoordinate2D(latitude: 37.0040, longitude: -121.5668),  // Gilroy
        "GTA": CLLocationCoordinate2D(latitude: 34.4377, longitude: -119.8431),  // Goleta
        "GUA": CLLocationCoordinate2D(latitude: 34.9629, longitude: -120.5734),  // Guadalupe
        "GVB": CLLocationCoordinate2D(latitude: 35.1213, longitude: -120.6293),  // Grover Beach
        "HAY": CLLocationCoordinate2D(latitude: 37.6660, longitude: -122.0993),  // Hayward
        "HNF": CLLocationCoordinate2D(latitude: 36.3261, longitude: -119.6518),  // Hanford
        "HSU": CLLocationCoordinate2D(latitude: 40.8733, longitude: -124.0815),  // Arcata
        "IRV": CLLocationCoordinate2D(latitude: 33.6568, longitude: -117.7337),  // Irvine
        "LOD": CLLocationCoordinate2D(latitude: 38.1332, longitude: -121.2719),  // Lodi
        "LPS": CLLocationCoordinate2D(latitude: 34.6827, longitude: -120.6050),  // Lompoc-Surf
        "LVS": CLLocationCoordinate2D(latitude: 36.1645, longitude: -115.1497),  // Las Vegas
        "MCD": CLLocationCoordinate2D(latitude: 37.3072, longitude: -120.4768),  // Merced
        "MRV": CLLocationCoordinate2D(latitude: 39.1437, longitude: -121.5973),  // Marysville
        "MTZ": CLLocationCoordinate2D(latitude: 38.0189, longitude: -122.1388),  // Martinez
        "MYU": CLLocationCoordinate2D(latitude: 36.6535, longitude: -121.8014),  // Seaside-Marina
        "NHL": CLLocationCoordinate2D(latitude: 34.3795, longitude: -118.5273),  // Santa Clarita-Newhall
        "NRG": CLLocationCoordinate2D(latitude: 34.2307, longitude: -118.5454),  // Northridge
        "OAC": CLLocationCoordinate2D(latitude: 37.7525, longitude: -122.1981),  // Oakland Coliseum/Airport
        "OKJ": CLLocationCoordinate2D(latitude: 37.7939, longitude: -122.2717),  // Oakland
        "ONA": CLLocationCoordinate2D(latitude: 34.0617, longitude: -117.6496),  // Ontario
        "OXN": CLLocationCoordinate2D(latitude: 34.1992, longitude: -119.1760),  // Oxnard
        "POS": CLLocationCoordinate2D(latitude: 34.0592, longitude: -117.7506),  // Pomona
        "PRB": CLLocationCoordinate2D(latitude: 35.6227, longitude: -120.6879),  // Paso Robles
        "PSN": CLLocationCoordinate2D(latitude: 33.8975, longitude: -116.5479),  // Palm Springs
        "PTC": CLLocationCoordinate2D(latitude: 38.2365, longitude: -122.6358),  // Petaluma
        "RDD": CLLocationCoordinate2D(latitude: 40.5836, longitude: -122.3934),  // Redding
        "RIC": CLLocationCoordinate2D(latitude: 37.9368, longitude: -122.3541),  // Richmond
        "RIV": CLLocationCoordinate2D(latitude: 33.9757, longitude: -117.3700),  // Riverside
        "RLN": CLLocationCoordinate2D(latitude: 38.7910, longitude: -121.2373),  // Rocklin
        "RSV": CLLocationCoordinate2D(latitude: 38.7500, longitude: -121.2863),  // Roseville
        "SCC": CLLocationCoordinate2D(latitude: 37.3532, longitude: -121.9366),  // Santa Clara
        "SFC": CLLocationCoordinate2D(latitude: 37.7886, longitude: -122.3989),  // San Francisco
        "SIM": CLLocationCoordinate2D(latitude: 34.2702, longitude: -118.6952),  // Simi Valley
        "SKN": CLLocationCoordinate2D(latitude: 37.9455, longitude: -121.2856),  // Stockton
        "SKT": CLLocationCoordinate2D(latitude: 37.9570, longitude: -121.2790),  // Stockton
        "SMN": CLLocationCoordinate2D(latitude: 34.0127, longitude: -118.4946),  // Santa Monica Pier
        "SNB": CLLocationCoordinate2D(latitude: 34.1041, longitude: -117.3107),  // San Bernardino
        "SNC": CLLocationCoordinate2D(latitude: 33.5013, longitude: -117.6638),  // San Juan Capistrano
        "SNP": CLLocationCoordinate2D(latitude: 33.4196, longitude: -117.6197),  // San Clemente Pier
        "SNS": CLLocationCoordinate2D(latitude: 36.6791, longitude: -121.6567),  // Salinas
        "SOL": CLLocationCoordinate2D(latitude: 32.9929, longitude: -117.2711),  // Solana Beach
        "SUI": CLLocationCoordinate2D(latitude: 38.2434, longitude: -122.0411),  // Suisun-Fairfield
        "VAL": CLLocationCoordinate2D(latitude: 38.1003, longitude: -122.2592),  // Vallejo
        "VEC": CLLocationCoordinate2D(latitude: 34.2769, longitude: -119.2999),  // Ventura
        "VNC": CLLocationCoordinate2D(latitude: 34.2113, longitude: -118.4482),  // Van Nuys
        "VRV": CLLocationCoordinate2D(latitude: 34.5372, longitude: -117.2930),  // Victorville
        "WNN": CLLocationCoordinate2D(latitude: 40.9690, longitude: -117.7322),  // Winnemucca
        "WTS": CLLocationCoordinate2D(latitude: 39.4126, longitude: -123.3510),  // Willits Calif Western Railroad Depot

        // Great Lakes
        "ALI": CLLocationCoordinate2D(latitude: 42.2472, longitude: -84.7558),  // Albion
        "ARB": CLLocationCoordinate2D(latitude: 42.2877, longitude: -83.7432),  // Ann Arbor
        "BAM": CLLocationCoordinate2D(latitude: 42.3145, longitude: -86.1116),  // Bangor
        "BTL": CLLocationCoordinate2D(latitude: 42.3185, longitude: -85.1878),  // Battle Creek
        "CBS": CLLocationCoordinate2D(latitude: 43.3406, longitude: -89.0126),  // Columbus
        "DER": CLLocationCoordinate2D(latitude: 42.3072, longitude: -83.2353),  // Dearborn
        "DRD": CLLocationCoordinate2D(latitude: 42.9095, longitude: -83.9823),  // Durand
        "ERI": CLLocationCoordinate2D(latitude: 42.1208, longitude: -80.0824),  // Erie
        "FLN": CLLocationCoordinate2D(latitude: 43.0154, longitude: -83.6517),  // Flint
        "GLN": CLLocationCoordinate2D(latitude: 42.0750, longitude: -87.8056),  // Glenview
        "HOM": CLLocationCoordinate2D(latitude: 42.7911, longitude: -86.0966),  // Holland
        "JXN": CLLocationCoordinate2D(latitude: 42.2481, longitude: -84.3997),  // Jackson
        "KAL": CLLocationCoordinate2D(latitude: 42.2953, longitude: -85.5840),  // Kalamazoo
        "LNS": CLLocationCoordinate2D(latitude: 42.7187, longitude: -84.4960),  // East Lansing
        "LPE": CLLocationCoordinate2D(latitude: 43.0495, longitude: -83.3062),  // Lapeer
        "MKA": CLLocationCoordinate2D(latitude: 42.9406, longitude: -87.9244),  // General Mitchell Intl. Airport
        "PNT": CLLocationCoordinate2D(latitude: 42.6328, longitude: -83.2923),  // Pontiac
        "POG": CLLocationCoordinate2D(latitude: 43.5471, longitude: -89.4676),  // Portage
        "PTH": CLLocationCoordinate2D(latitude: 42.9604, longitude: -82.4438),  // Port Huron
        "ROY": CLLocationCoordinate2D(latitude: 42.4884, longitude: -83.1470),  // Royal Oak
        "SVT": CLLocationCoordinate2D(latitude: 42.7183, longitude: -87.9063),  // Sturtevant
        "TRM": CLLocationCoordinate2D(latitude: 42.5426, longitude: -83.1910),  // Troy
        "WDL": CLLocationCoordinate2D(latitude: 43.6265, longitude: -89.7775),  // Wisconsin Dells

        // Mid-Atlantic
        "ALT": CLLocationCoordinate2D(latitude: 40.5145, longitude: -78.4016),  // Altoona
        "ARD": CLLocationCoordinate2D(latitude: 40.0083, longitude: -75.2904),  // Ardmore
        "BER": CLLocationCoordinate2D(latitude: 41.6356, longitude: -72.7653),  // Berlin
        "BNF": CLLocationCoordinate2D(latitude: 41.2745, longitude: -72.8172),  // Branford
        "BWE": CLLocationCoordinate2D(latitude: 39.0178, longitude: -76.7650),  // Bowie State
        "CLN": CLLocationCoordinate2D(latitude: 41.2795, longitude: -72.5283),  // Clinton
        "COV": CLLocationCoordinate2D(latitude: 40.0203, longitude: -79.5928),  // Connellsville
        "CRT": CLLocationCoordinate2D(latitude: 41.1899, longitude: -73.8824),  // Croton-Harmon
        "CUM": CLLocationCoordinate2D(latitude: 39.6506, longitude: -78.7580),  // Cumberland
        "CWH": CLLocationCoordinate2D(latitude: 40.0717, longitude: -74.9522),  // Cornwells Heights
        "EDG": CLLocationCoordinate2D(latitude: 39.4162, longitude: -76.2928),  // Edgewood
        "GNB": CLLocationCoordinate2D(latitude: 40.3050, longitude: -79.5469),  // Greensburg
        "GUI": CLLocationCoordinate2D(latitude: 41.2756, longitude: -72.6735),  // Guilford
        "HAE": CLLocationCoordinate2D(latitude: 39.2372, longitude: -76.6915),  // Halethorpe
        "HFY": CLLocationCoordinate2D(latitude: 39.3245, longitude: -77.7311),  // Harpers Ferry
        "HGD": CLLocationCoordinate2D(latitude: 40.4837, longitude: -78.0118),  // Huntingdon
        "JST": CLLocationCoordinate2D(latitude: 40.3297, longitude: -78.9220),  // Johnstown
        "LAB": CLLocationCoordinate2D(latitude: 40.3174, longitude: -79.3851),  // Latrobe
        "LEW": CLLocationCoordinate2D(latitude: 40.5883, longitude: -77.5800),  // Lewistown
        "MDS": CLLocationCoordinate2D(latitude: 41.2836, longitude: -72.5994),  // Madison
        "MID": CLLocationCoordinate2D(latitude: 40.1957, longitude: -76.7365),  // Middletown
        "MRB": CLLocationCoordinate2D(latitude: 39.4587, longitude: -77.9610),  // Martinsburg
        "MSA": CLLocationCoordinate2D(latitude: 39.3301, longitude: -76.4214),  // Martin Airport
        "MYS": CLLocationCoordinate2D(latitude: 41.3509, longitude: -71.9631),  // Mystic
        "NRK": CLLocationCoordinate2D(latitude: 39.6697, longitude: -75.7535),  // Newark, DE
        "NRO": CLLocationCoordinate2D(latitude: 40.9115, longitude: -73.7843),  // New Rochelle
        "OTN": CLLocationCoordinate2D(latitude: 39.0871, longitude: -76.7064),  // Odenton
        "PAR": CLLocationCoordinate2D(latitude: 39.9592, longitude: -75.9221),  // Parkesburg
        "PHN": CLLocationCoordinate2D(latitude: 39.9968, longitude: -75.1551),  // North Philadelphia
        "POU": CLLocationCoordinate2D(latitude: 41.7071, longitude: -73.9375),  // Poughkeepsie
        "PRV": CLLocationCoordinate2D(latitude: 39.5580, longitude: -76.0732),  // Perryville
        "RHI": CLLocationCoordinate2D(latitude: 41.9213, longitude: -73.9513),  // Rhinecliff
        "RKV": CLLocationCoordinate2D(latitude: 39.0845, longitude: -77.1460),  // Rockville
        "STS": CLLocationCoordinate2D(latitude: 41.3053, longitude: -72.9221),  // New Haven
        "TYR": CLLocationCoordinate2D(latitude: 40.6677, longitude: -78.2405),  // Tyrone
        "WBL": CLLocationCoordinate2D(latitude: 39.2934, longitude: -76.6533),  // West Baltimore
        "WND": CLLocationCoordinate2D(latitude: 41.8520, longitude: -72.6423),  // Windsor
        "WSB": CLLocationCoordinate2D(latitude: 41.2888, longitude: -72.4480),  // Westbrook
        "YNY": CLLocationCoordinate2D(latitude: 40.9356, longitude: -73.9023),  // Yonkers

        // Midwest
        "AKY": CLLocationCoordinate2D(latitude: 38.4809, longitude: -82.6396),  // Ashland
        "ALC": CLLocationCoordinate2D(latitude: 40.9213, longitude: -81.0929),  // Alliance
        "ALD": CLLocationCoordinate2D(latitude: 37.7243, longitude: -80.6449),  // Alderson
        "BNL": CLLocationCoordinate2D(latitude: 40.5090, longitude: -88.9843),  // Bloomington-Normal
        "BYN": CLLocationCoordinate2D(latitude: 41.4803, longitude: -84.5518),  // Bryan
        "CDL": CLLocationCoordinate2D(latitude: 37.7242, longitude: -89.2166),  // Carbondale
        "CEN": CLLocationCoordinate2D(latitude: 38.5275, longitude: -89.1361),  // Centralia
        "CHM": CLLocationCoordinate2D(latitude: 40.1158, longitude: -88.2414),  // Champaign-Urbana
        "CHW": CLLocationCoordinate2D(latitude: 38.3464, longitude: -81.6385),  // Charleston
        "COI": CLLocationCoordinate2D(latitude: 39.6460, longitude: -85.1334),  // Connersville
        "CRF": CLLocationCoordinate2D(latitude: 40.0447, longitude: -86.8992),  // Crawfordsville
        "CRV": CLLocationCoordinate2D(latitude: 39.2793, longitude: -89.8893),  // Carlinville
        "DOA": CLLocationCoordinate2D(latitude: 41.9809, longitude: -86.1090),  // Dowagiac
        "DQN": CLLocationCoordinate2D(latitude: 38.0123, longitude: -89.2403),  // Du Quoin
        "DWT": CLLocationCoordinate2D(latitude: 41.0899, longitude: -88.4307),  // Dwight
        "DYE": CLLocationCoordinate2D(latitude: 41.5154, longitude: -87.5181),  // Dyer
        "EFG": CLLocationCoordinate2D(latitude: 39.1171, longitude: -88.5471),  // Effingham
        "EKH": CLLocationCoordinate2D(latitude: 41.6807, longitude: -85.9718),  // Elkhart
        "ELY": CLLocationCoordinate2D(latitude: 41.3700, longitude: -82.0967),  // Elyria
        "FTN": CLLocationCoordinate2D(latitude: 36.5257, longitude: -88.8888),  // Fulton
        "GLM": CLLocationCoordinate2D(latitude: 40.7525, longitude: -87.9981),  // Gilman
        "HIN": CLLocationCoordinate2D(latitude: 37.6750, longitude: -80.8922),  // Hinton
        "HMI": CLLocationCoordinate2D(latitude: 41.6912, longitude: -87.5065),  // Hammond-Whiting
        "HMW": CLLocationCoordinate2D(latitude: 41.5624, longitude: -87.6687),  // Homewood
        "JOL": CLLocationCoordinate2D(latitude: 41.5246, longitude: -88.0787),  // Joliet Gateway Center
        "KAN": CLLocationCoordinate2D(latitude: 35.4962, longitude: -80.6249),  // Kannapolis
        "KEE": CLLocationCoordinate2D(latitude: 41.2458, longitude: -89.9275),  // Kewanee
        "KKI": CLLocationCoordinate2D(latitude: 41.1193, longitude: -87.8654),  // Kankakee
        "LAF": CLLocationCoordinate2D(latitude: 40.4193, longitude: -86.8959),  // Lafayette
        "LAG": CLLocationCoordinate2D(latitude: 41.8156, longitude: -87.8715),  // La Grange
        "LCN": CLLocationCoordinate2D(latitude: 40.1482, longitude: -89.3631),  // Lincoln
        "MAT": CLLocationCoordinate2D(latitude: 39.4827, longitude: -88.3760),  // Mattoon
        "MAY": CLLocationCoordinate2D(latitude: 38.6521, longitude: -83.7711),  // Maysville
        "MDT": CLLocationCoordinate2D(latitude: 41.5496, longitude: -89.1179),  // Mendota
        "MNG": CLLocationCoordinate2D(latitude: 38.1807, longitude: -81.3240),  // Montgomery
        "NBN": CLLocationCoordinate2D(latitude: 36.1127, longitude: -89.2623),  // Newbern-Dyersburg
        "NBU": CLLocationCoordinate2D(latitude: 41.7967, longitude: -86.7458),  // New Buffalo
        "NLS": CLLocationCoordinate2D(latitude: 41.8374, longitude: -86.2524),  // Niles
        "NPV": CLLocationCoordinate2D(latitude: 41.7795, longitude: -88.1455),  // Naperville
        "PCT": CLLocationCoordinate2D(latitude: 41.3852, longitude: -89.4668),  // Princeton
        "PIA": CLLocationCoordinate2D(latitude: 40.6894, longitude: -89.5936),  // Peoria
        "PLO": CLLocationCoordinate2D(latitude: 41.6624, longitude: -88.5383),  // Plano
        "PON": CLLocationCoordinate2D(latitude: 40.8787, longitude: -88.6372),  // Pontiac
        "PRC": CLLocationCoordinate2D(latitude: 37.8566, longitude: -81.0607),  // Prince
        "REN": CLLocationCoordinate2D(latitude: 40.9433, longitude: -87.1551),  // Rensselaer
        "RTL": CLLocationCoordinate2D(latitude: 40.3109, longitude: -88.1591),  // Rantoul
        "SKY": CLLocationCoordinate2D(latitude: 41.4407, longitude: -82.7179),  // Sandusky
        "SMT": CLLocationCoordinate2D(latitude: 41.7949, longitude: -87.8097),  // Summit
        "SOB": CLLocationCoordinate2D(latitude: 41.6784, longitude: -86.2873),  // South Bend
        "SPI": CLLocationCoordinate2D(latitude: 39.8023, longitude: -89.6514),  // Springfield
        "SPM": CLLocationCoordinate2D(latitude: 38.7213, longitude: -82.9638),  // South Portsmouth
        "THN": CLLocationCoordinate2D(latitude: 37.9570, longitude: -81.0788),  // Thurmond
        "WSS": CLLocationCoordinate2D(latitude: 37.7864, longitude: -80.3040),  // White Sulphur Springs
        "WTI": CLLocationCoordinate2D(latitude: 41.4318, longitude: -85.0243),  // Waterloo

        // Mountain West
        "ACD": CLLocationCoordinate2D(latitude: 37.5922, longitude: -90.6244),  // Arcadia Valley
        "ADM": CLLocationCoordinate2D(latitude: 34.1725, longitude: -97.1255),  // Ardmore
        "ALN": CLLocationCoordinate2D(latitude: 38.9210, longitude: -90.1573),  // Alton
        "ALP": CLLocationCoordinate2D(latitude: 30.3573, longitude: -103.6615),  // Alpine
        "ARK": CLLocationCoordinate2D(latitude: 34.1139, longitude: -93.0533),  // Arkadelphia
        "BMT": CLLocationCoordinate2D(latitude: 30.0765, longitude: -94.1274),  // Beaumont
        "BRH": CLLocationCoordinate2D(latitude: 31.5830, longitude: -90.4411),  // Brookhaven
        "BRL": CLLocationCoordinate2D(latitude: 40.8058, longitude: -91.1020),  // Burlington
        "CBR": CLLocationCoordinate2D(latitude: 32.3497, longitude: -97.3823),  // Cleburne
        "CRN": CLLocationCoordinate2D(latitude: 41.0569, longitude: -94.3616),  // Creston
        "DDG": CLLocationCoordinate2D(latitude: 37.7523, longitude: -100.0170),  // Dodge City
        "DLK": CLLocationCoordinate2D(latitude: 46.8197, longitude: -95.8460),  // Detroit Lakes
        "DRT": CLLocationCoordinate2D(latitude: 29.3622, longitude: -100.9027),  // Del Rio
        "DVL": CLLocationCoordinate2D(latitude: 48.1105, longitude: -98.8614),  // Devils Lake
        "FAR": CLLocationCoordinate2D(latitude: 46.8810, longitude: -96.7854),  // Fargo
        "FMG": CLLocationCoordinate2D(latitude: 40.2472, longitude: -103.8028),  // Fort Morgan
        "GBB": CLLocationCoordinate2D(latitude: 40.9447, longitude: -90.3641),  // Galesburg
        "GCK": CLLocationCoordinate2D(latitude: 37.9644, longitude: -100.8733),  // Garden City
        "GFK": CLLocationCoordinate2D(latitude: 47.9175, longitude: -97.1108),  // Grand Forks
        "GLE": CLLocationCoordinate2D(latitude: 33.6252, longitude: -97.1409),  // Gainesville
        "GWD": CLLocationCoordinate2D(latitude: 33.5172, longitude: -90.1765),  // Greenwood
        "HAS": CLLocationCoordinate2D(latitude: 40.5843, longitude: -98.3875),  // Hastings
        "HAZ": CLLocationCoordinate2D(latitude: 31.8613, longitude: -90.3943),  // Hazlehurst
        "HLD": CLLocationCoordinate2D(latitude: 40.4360, longitude: -99.3701),  // Holdrege
        "HMD": CLLocationCoordinate2D(latitude: 30.5072, longitude: -90.4622),  // Hammond
        "HOP": CLLocationCoordinate2D(latitude: 33.6689, longitude: -93.5922),  // Hope
        "HUT": CLLocationCoordinate2D(latitude: 38.0557, longitude: -97.9315),  // Hutchinson
        "IDP": CLLocationCoordinate2D(latitude: 39.0869, longitude: -94.4297),  // Independence
        "JAN": CLLocationCoordinate2D(latitude: 32.3008, longitude: -90.1909),  // Jackson
        "JEF": CLLocationCoordinate2D(latitude: 38.5789, longitude: -92.1699),  // Jefferson City
        "KIL": CLLocationCoordinate2D(latitude: 31.1212, longitude: -97.7286),  // Killeen
        "KWD": CLLocationCoordinate2D(latitude: 38.5811, longitude: -90.4068),  // Kirkwood
        "LAJ": CLLocationCoordinate2D(latitude: 37.9882, longitude: -103.5436),  // La Junta
        "LAP": CLLocationCoordinate2D(latitude: 40.0292, longitude: -92.4934),  // La Plata
        "LBO": CLLocationCoordinate2D(latitude: 54.7740, longitude: -101.8481),  // Lbo
        "LCH": CLLocationCoordinate2D(latitude: 30.2381, longitude: -93.2170),  // Lake Charles
        "LEE": CLLocationCoordinate2D(latitude: 38.9126, longitude: -94.3780),  // Lee'S Summit
        "LFT": CLLocationCoordinate2D(latitude: 30.2265, longitude: -92.0145),  // Lafayette
        "LRC": CLLocationCoordinate2D(latitude: 38.9712, longitude: -95.2305),  // Lawrence
        "LSE": CLLocationCoordinate2D(latitude: 43.8332, longitude: -91.2473),  // La Crosse
        "MAC": CLLocationCoordinate2D(latitude: 40.4612, longitude: -90.6709),  // Macomb
        "MCB": CLLocationCoordinate2D(latitude: 31.2445, longitude: -90.4513),  // Mccomb
        "MCG": CLLocationCoordinate2D(latitude: 31.4434, longitude: -97.4048),  // Mcgregor
        "MCK": CLLocationCoordinate2D(latitude: 40.1976, longitude: -100.6258),  // Mccook
        "MKS": CLLocationCoordinate2D(latitude: 34.2582, longitude: -90.2723),  // Marks
        "MOT": CLLocationCoordinate2D(latitude: 48.2361, longitude: -101.2986),  // Minot
        "MTP": CLLocationCoordinate2D(latitude: 40.9712, longitude: -91.5508),  // Mt. Pleasant
        "NIB": CLLocationCoordinate2D(latitude: 30.0084, longitude: -91.8238),  // New Iberia
        "NOR": CLLocationCoordinate2D(latitude: 35.2200, longitude: -97.4430),  // Norman
        "OSC": CLLocationCoordinate2D(latitude: 41.0371, longitude: -93.7649),  // Osceola
        "OTM": CLLocationCoordinate2D(latitude: 41.0188, longitude: -92.4149),  // Ottumwa
        "PBF": CLLocationCoordinate2D(latitude: 36.7540, longitude: -90.3933),  // Poplar Bluff
        "PUR": CLLocationCoordinate2D(latitude: 35.0120, longitude: -97.3574),  // Purcell
        "PVL": CLLocationCoordinate2D(latitude: 34.7417, longitude: -97.2185),  // Pauls Valley
        "QCY": CLLocationCoordinate2D(latitude: 39.9571, longitude: -91.3685),  // Quincy
        "RAT": CLLocationCoordinate2D(latitude: 36.9011, longitude: -104.4379),  // Raton
        "RDW": CLLocationCoordinate2D(latitude: 44.5662, longitude: -92.5371),  // Red Wing
        "RUG": CLLocationCoordinate2D(latitude: 48.3698, longitude: -99.9976),  // Rugby
        "SCD": CLLocationCoordinate2D(latitude: 45.5677, longitude: -94.1491),  // St. Cloud
        "SCH": CLLocationCoordinate2D(latitude: 29.7467, longitude: -90.8152),  // Schriever
        "SED": CLLocationCoordinate2D(latitude: 38.7116, longitude: -93.2287),  // Sedalia
        "SHR": CLLocationCoordinate2D(latitude: 32.4997, longitude: -93.7567),  // Shreveport Sportran Intermodal Terminal
        "SMC": CLLocationCoordinate2D(latitude: 29.8766, longitude: -97.9410),  // San Marcos
        "SND": CLLocationCoordinate2D(latitude: 30.1400, longitude: -102.3987),  // Sanderson
        "SPL": CLLocationCoordinate2D(latitude: 46.3546, longitude: -94.7953),  // Staples
        "TAY": CLLocationCoordinate2D(latitude: 30.5677, longitude: -97.4078),  // Taylor
        "TOH": CLLocationCoordinate2D(latitude: 43.9860, longitude: -90.5053),  // Tomah
        "TOP": CLLocationCoordinate2D(latitude: 39.0514, longitude: -95.6649),  // Topeka
        "TPL": CLLocationCoordinate2D(latitude: 31.0959, longitude: -97.3458),  // Temple
        "TRI": CLLocationCoordinate2D(latitude: 37.1727, longitude: -104.5080),  // Trinidad
        "TXA": CLLocationCoordinate2D(latitude: 33.4201, longitude: -94.0431),  // Texarkana
        "WAH": CLLocationCoordinate2D(latitude: 38.5615, longitude: -91.0127),  // Washington
        "WAR": CLLocationCoordinate2D(latitude: 38.7627, longitude: -93.7409),  // Warrensburg
        "WEL": CLLocationCoordinate2D(latitude: 37.2749, longitude: -97.3818),  // Wellington
        "WIC": CLLocationCoordinate2D(latitude: 37.6847, longitude: -97.3341),  // Wichita
        "WIN": CLLocationCoordinate2D(latitude: 44.0444, longitude: -91.6401),  // Winona
        "WNR": CLLocationCoordinate2D(latitude: 36.0677, longitude: -90.9568),  // Walnut Ridge
        "WTN": CLLocationCoordinate2D(latitude: 48.1430, longitude: -103.6209),  // Williston
        "YAZ": CLLocationCoordinate2D(latitude: 32.8485, longitude: -90.4152),  // Yazoo City

        // New England
        "AMS": CLLocationCoordinate2D(latitude: 42.9537, longitude: -74.2195),  // Amsterdam
        "AST": CLLocationCoordinate2D(latitude: 43.3134, longitude: -79.8557),  // Aldershot
        "BFX": CLLocationCoordinate2D(latitude: 42.8784, longitude: -78.8737),  // Buffalo
        "BLF": CLLocationCoordinate2D(latitude: 43.1365, longitude: -72.4446),  // Bellows Falls
        "BON": CLLocationCoordinate2D(latitude: 42.3662, longitude: -71.0611),  // Boston North
        "BRA": CLLocationCoordinate2D(latitude: 42.8508, longitude: -72.5565),  // Brattleboro
        "BRK": CLLocationCoordinate2D(latitude: 43.9114, longitude: -69.9655),  // Brunswick
        "CBN": CLLocationCoordinate2D(latitude: 43.1092, longitude: -79.0584),  // Canadian Border
        "CNV": CLLocationCoordinate2D(latitude: 43.6134, longitude: -73.1713),  // Castleton
        "FED": CLLocationCoordinate2D(latitude: 43.2696, longitude: -73.5806),  // Fort Edward
        "FRA": CLLocationCoordinate2D(latitude: 42.2760, longitude: -71.4200),  // Framingham
        "FRE": CLLocationCoordinate2D(latitude: 43.8550, longitude: -70.1024),  // Freeport
        "FTC": CLLocationCoordinate2D(latitude: 43.8538, longitude: -73.3897),  // Ticonderoga
        "GFD": CLLocationCoordinate2D(latitude: 42.5855, longitude: -72.6008),  // Greenfield
        "GMS": CLLocationCoordinate2D(latitude: 43.1959, longitude: -79.5579),  // Grimsby
        "HHL": CLLocationCoordinate2D(latitude: 42.7733, longitude: -71.0864),  // Haverhill
        "HLK": CLLocationCoordinate2D(latitude: 42.2042, longitude: -72.6023),  // Holyoke
        "HUD": CLLocationCoordinate2D(latitude: 42.2539, longitude: -73.7977),  // Hudson
        "MBY": CLLocationCoordinate2D(latitude: 44.0174, longitude: -73.1698),  // Middlebury
        "MPR": CLLocationCoordinate2D(latitude: 44.2557, longitude: -72.6064),  // Montpelier-Berlin
        "NFL": CLLocationCoordinate2D(latitude: 43.1099, longitude: -79.0553),  // Niagara Falls
        "NFS": CLLocationCoordinate2D(latitude: 43.1087, longitude: -79.0633),  // Niagara Falls
        "NHT": CLLocationCoordinate2D(latitude: 42.3189, longitude: -72.6264),  // Northampton
        "OKL": CLLocationCoordinate2D(latitude: 43.4554, longitude: -79.6824),  // Oakville
        "ORB": CLLocationCoordinate2D(latitude: 43.5143, longitude: -70.3762),  // Old Orchard Beach
        "PIT": CLLocationCoordinate2D(latitude: 42.4516, longitude: -73.2538),  // Pittsfield
        "PLB": CLLocationCoordinate2D(latitude: 44.6967, longitude: -73.4463),  // Plattsburgh
        "POH": CLLocationCoordinate2D(latitude: 44.0423, longitude: -73.4588),  // Port Henry
        "ROM": CLLocationCoordinate2D(latitude: 43.1994, longitude: -75.4500),  // Rome
        "RPH": CLLocationCoordinate2D(latitude: 43.9224, longitude: -72.6655),  // Randolph
        "RSP": CLLocationCoordinate2D(latitude: 44.9949, longitude: -73.3711),  // Rouses Point
        "RTE": CLLocationCoordinate2D(latitude: 42.2102, longitude: -71.1479),  // Route 128
        "RUD": CLLocationCoordinate2D(latitude: 43.6058, longitude: -72.9815),  // Rutland
        "SAO": CLLocationCoordinate2D(latitude: 43.4962, longitude: -70.4491),  // Saco
        "SAR": CLLocationCoordinate2D(latitude: 43.0828, longitude: -73.8100),  // Saratoga Springs
        "SCA": CLLocationCoordinate2D(latitude: 43.1478, longitude: -79.2560),  // St. Catherines
        "SDY": CLLocationCoordinate2D(latitude: 42.8147, longitude: -73.9429),  // Schenectady
        "SLQ": CLLocationCoordinate2D(latitude: 45.4989, longitude: -73.5073),  // St-Lambert
        "TWO": CLLocationCoordinate2D(latitude: 43.6454, longitude: -79.3808),  // Toronto
        "UCA": CLLocationCoordinate2D(latitude: 43.1039, longitude: -75.2234),  // Utica
        "VRN": CLLocationCoordinate2D(latitude: 44.1809, longitude: -73.2488),  // Ferrisburgh
        "WAB": CLLocationCoordinate2D(latitude: 44.3350, longitude: -72.7518),  // Waterbury-Stowe
        "WEM": CLLocationCoordinate2D(latitude: 43.3208, longitude: -70.6122),  // Wells
        "WHL": CLLocationCoordinate2D(latitude: 43.5547, longitude: -73.4032),  // Whitehall
        "WNM": CLLocationCoordinate2D(latitude: 43.4799, longitude: -72.3850),  // Windsor-Mt. Ascutney
        "WOB": CLLocationCoordinate2D(latitude: 42.5174, longitude: -71.1438),  // Woburn
        "WOR": CLLocationCoordinate2D(latitude: 42.2615, longitude: -71.7948),  // Worcester Union
        "WRJ": CLLocationCoordinate2D(latitude: 43.6478, longitude: -72.3173),  // White River Junction
        "WSP": CLLocationCoordinate2D(latitude: 44.1873, longitude: -73.4518),  // Westport

        // Pacific Northwest
        "ALY": CLLocationCoordinate2D(latitude: 44.6305, longitude: -123.1028),  // Albany
        "BEL": CLLocationCoordinate2D(latitude: 48.7203, longitude: -122.5113),  // Bellingham
        "BNG": CLLocationCoordinate2D(latitude: 45.7150, longitude: -121.4687),  // Bingen-White Salmon
        "BRO": CLLocationCoordinate2D(latitude: 48.5341, longitude: -113.0132),  // Browning
        "CMO": CLLocationCoordinate2D(latitude: 43.2168, longitude: -121.7816),  // Chemult
        "CTL": CLLocationCoordinate2D(latitude: 46.7175, longitude: -122.9531),  // Centralia
        "CUT": CLLocationCoordinate2D(latitude: 48.6384, longitude: -112.3316),  // Cut Bank
        "EDM": CLLocationCoordinate2D(latitude: 47.8111, longitude: -122.3841),  // Edmonds
        "EPH": CLLocationCoordinate2D(latitude: 47.3209, longitude: -119.5493),  // Ephrata
        "ESM": CLLocationCoordinate2D(latitude: 48.2755, longitude: -113.6109),  // Essex
        "EVR": CLLocationCoordinate2D(latitude: 47.9754, longitude: -122.1979),  // Everett
        "GGW": CLLocationCoordinate2D(latitude: 48.1949, longitude: -106.6362),  // Glasgow
        "GRA": CLLocationCoordinate2D(latitude: 40.0842, longitude: -105.9355),  // Granby
        "KEL": CLLocationCoordinate2D(latitude: 46.1423, longitude: -122.9130),  // Kelso-Longview
        "KFS": CLLocationCoordinate2D(latitude: 42.2255, longitude: -121.7720),  // Klamath Falls
        "LIB": CLLocationCoordinate2D(latitude: 48.3948, longitude: -115.5489),  // Libby
        "LWA": CLLocationCoordinate2D(latitude: 47.6065, longitude: -120.6440),  // Leavenworth
        "MAL": CLLocationCoordinate2D(latitude: 48.3605, longitude: -107.8722),  // Malta
        "MVW": CLLocationCoordinate2D(latitude: 48.4185, longitude: -122.3347),  // Mount Vernon
        "OLW": CLLocationCoordinate2D(latitude: 46.9913, longitude: -122.7941),  // Olympia-Lacey
        "ORC": CLLocationCoordinate2D(latitude: 45.3661, longitude: -122.5959),  // Oregon City
        "PRO": CLLocationCoordinate2D(latitude: 40.2260, longitude: -111.6640),  // Provo
        "PSC": CLLocationCoordinate2D(latitude: 46.2370, longitude: -119.0877),  // Pasco
        "SBY": CLLocationCoordinate2D(latitude: 48.5067, longitude: -111.8566),  // Shelby
        "SPT": CLLocationCoordinate2D(latitude: 48.2762, longitude: -116.5456),  // Sandpoint
        "STW": CLLocationCoordinate2D(latitude: 48.2426, longitude: -122.3499),  // Stanwood
        "TUK": CLLocationCoordinate2D(latitude: 47.4611, longitude: -122.2403),  // Tukwila
        "VAC": CLLocationCoordinate2D(latitude: 49.2738, longitude: -123.0983),  // Vancouver
        "VAN": CLLocationCoordinate2D(latitude: 45.6289, longitude: -122.6865),  // Vancouver
        "WEN": CLLocationCoordinate2D(latitude: 47.4216, longitude: -120.3066),  // Wenatchee
        "WGL": CLLocationCoordinate2D(latitude: 48.4962, longitude: -113.9792),  // West Glacier
        "WIH": CLLocationCoordinate2D(latitude: 45.6577, longitude: -120.9661),  // Wishram
        "WPT": CLLocationCoordinate2D(latitude: 48.0917, longitude: -105.6427),  // Wolf Point

        // South Central
        "ATN": CLLocationCoordinate2D(latitude: 33.6491, longitude: -85.8321),  // Anniston
        "BAS": CLLocationCoordinate2D(latitude: 30.3087, longitude: -89.3340),  // Bay St Louis
        "BDT": CLLocationCoordinate2D(latitude: 27.5285, longitude: -82.5123),  // Bradenton
        "BIX": CLLocationCoordinate2D(latitude: 30.3991, longitude: -88.8916),  // Biloxi Amtrak Sta
        "CAM": CLLocationCoordinate2D(latitude: 34.2482, longitude: -80.6252),  // Camden
        "DFB": CLLocationCoordinate2D(latitude: 26.3171, longitude: -80.1221),  // Deerfield Beach
        "DNK": CLLocationCoordinate2D(latitude: 33.3262, longitude: -81.1436),  // Denmark
        "GNS": CLLocationCoordinate2D(latitude: 34.2889, longitude: -83.8197),  // Gainesville
        "GUF": CLLocationCoordinate2D(latitude: 30.3690, longitude: -89.0948),  // Gulfport Amtrak Sta
        "HBG": CLLocationCoordinate2D(latitude: 31.3269, longitude: -89.2865),  // Hattiesburg
        "JSP": CLLocationCoordinate2D(latitude: 31.6056, longitude: -81.8822),  // Jesup
        "LAK": CLLocationCoordinate2D(latitude: 28.0456, longitude: -81.9519),  // Lakeland
        "LAU": CLLocationCoordinate2D(latitude: 31.6922, longitude: -89.1279),  // Laurel
        "MEI": CLLocationCoordinate2D(latitude: 32.3642, longitude: -88.6966),  // Meridian Union
        "OKE": CLLocationCoordinate2D(latitude: 27.2519, longitude: -80.8308),  // Okeechobee
        "PAG": CLLocationCoordinate2D(latitude: 30.3678, longitude: -88.5595),  // Pascagoula
        "PAK": CLLocationCoordinate2D(latitude: 29.6497, longitude: -81.6405),  // Palatka
        "PIC": CLLocationCoordinate2D(latitude: 30.5246, longitude: -89.6803),  // Picayune
        "SBG": CLLocationCoordinate2D(latitude: 27.4966, longitude: -81.4342),  // Sebring
        "SDL": CLLocationCoordinate2D(latitude: 30.2784, longitude: -89.7826),  // Slidell
        "SFA": CLLocationCoordinate2D(latitude: 28.8085, longitude: -81.2913),  // Sanford Amtrak Auto Train
        "STP": CLLocationCoordinate2D(latitude: 27.8430, longitude: -82.6444),  // St. Petersburg
        "TCA": CLLocationCoordinate2D(latitude: 34.5785, longitude: -83.3315),  // Toccoa
        "TCL": CLLocationCoordinate2D(latitude: 33.1932, longitude: -87.5602),  // Tuscaloosa
        "WDO": CLLocationCoordinate2D(latitude: 29.7905, longitude: -82.1667),  // Waldo
        "YEM": CLLocationCoordinate2D(latitude: 32.6883, longitude: -80.8469),  // Yemassee

        // Southeast
        "BCV": CLLocationCoordinate2D(latitude: 38.7973, longitude: -77.2988),  // Burke Centre
        "BNC": CLLocationCoordinate2D(latitude: 36.0942, longitude: -79.4345),  // Burlington
        "CLF": CLLocationCoordinate2D(latitude: 37.8145, longitude: -79.8274),  // Clifton Forge
        "CYN": CLLocationCoordinate2D(latitude: 35.7883, longitude: -78.7822),  // Cary
        "DAN": CLLocationCoordinate2D(latitude: 36.5841, longitude: -79.3840),  // Danville
        "FAY": CLLocationCoordinate2D(latitude: 35.0550, longitude: -78.8848),  // Fayetteville
        "FBG": CLLocationCoordinate2D(latitude: 38.2984, longitude: -77.4572),  // Fredericksburg
        "GBO": CLLocationCoordinate2D(latitude: 35.3857, longitude: -78.0033),  // Goldsboro
        "GRO": CLLocationCoordinate2D(latitude: 36.0698, longitude: -79.7871),  // Greensboro
        "KNC": CLLocationCoordinate2D(latitude: 35.2437, longitude: -77.5845),  // Kinston
        "MHD": CLLocationCoordinate2D(latitude: 34.7214, longitude: -76.7157),  // Morehead City
        "QAN": CLLocationCoordinate2D(latitude: 38.5219, longitude: -77.2930),  // Quantico
        "SEB": CLLocationCoordinate2D(latitude: 38.9727, longitude: -76.8436),  // Seabrook
        "SOP": CLLocationCoordinate2D(latitude: 35.1751, longitude: -79.3903),  // Southern Pines
        "STA": CLLocationCoordinate2D(latitude: 38.1476, longitude: -79.0718),  // Staunton
        "SWB": CLLocationCoordinate2D(latitude: 34.6971, longitude: -77.1396),  // Swansboro
        "WDB": CLLocationCoordinate2D(latitude: 38.6589, longitude: -77.2479),  // Woodbridge
        "WMN": CLLocationCoordinate2D(latitude: 34.2512, longitude: -77.8749),  // Wilmington

        // Southwest
        "BEN": CLLocationCoordinate2D(latitude: 31.9688, longitude: -110.2969),  // Benson
        "DEM": CLLocationCoordinate2D(latitude: 32.2718, longitude: -107.7543),  // Deming
        "GJT": CLLocationCoordinate2D(latitude: 39.0644, longitude: -108.5699),  // Grand Junction
        "GLP": CLLocationCoordinate2D(latitude: 35.5292, longitude: -108.7405),  // Gallup
        "GRI": CLLocationCoordinate2D(latitude: 38.9920, longitude: -110.1652),  // Green River
        "GSC": CLLocationCoordinate2D(latitude: 39.5479, longitude: -107.3232),  // Glenwood Springs
        "HER": CLLocationCoordinate2D(latitude: 39.6840, longitude: -110.8539),  // Helper
        "KNG": CLLocationCoordinate2D(latitude: 35.1883, longitude: -114.0528),  // Kingman
        "LDB": CLLocationCoordinate2D(latitude: 32.3501, longitude: -108.7070),  // Lordsburg
        "LMY": CLLocationCoordinate2D(latitude: 35.4810, longitude: -105.8800),  // Lamy
        "LSV": CLLocationCoordinate2D(latitude: 35.5934, longitude: -105.2128),  // Las Vegas
        "MRC": CLLocationCoordinate2D(latitude: 33.0563, longitude: -112.0471),  // Maricopa
        "NDL": CLLocationCoordinate2D(latitude: 34.8406, longitude: -114.6062),  // Needles
        "PHA": CLLocationCoordinate2D(latitude: 33.4364, longitude: -112.0130),  // Phoenix Sky Harbor Airport
        "PXN": CLLocationCoordinate2D(latitude: 33.6395, longitude: -112.1192),  // North Phoenix Metro Center Transit
        "SAF": CLLocationCoordinate2D(latitude: 35.6843, longitude: -105.9466),  // Santa Fe
        "WIP": CLLocationCoordinate2D(latitude: 39.9476, longitude: -105.8174),  // Winter Park/Fraser
        "WLO": CLLocationCoordinate2D(latitude: 35.0217, longitude: -110.6950),  // Winslow
        "WMH": CLLocationCoordinate2D(latitude: 35.2511, longitude: -112.1981),  // Williams
        "WPR": CLLocationCoordinate2D(latitude: 39.8876, longitude: -105.7632),  // Winter Park Ski Resort
        "WPS": CLLocationCoordinate2D(latitude: 39.8837, longitude: -105.7618),  // Winter Park
        "YUM": CLLocationCoordinate2D(latitude: 32.7231, longitude: -114.6156),  // Yuma


        // LIRR stations (Long Island Rail Road)
        "ABT": CLLocationCoordinate2D(latitude: 40.77206317, longitude: -73.64169095),  // Albertson
        "AGT": CLLocationCoordinate2D(latitude: 40.98003964, longitude: -72.13233416),  // Amagansett
        "AVL": CLLocationCoordinate2D(latitude: 40.68024859, longitude: -73.42031192),  // Amityville
        "LAT": CLLocationCoordinate2D(latitude: 40.68359596, longitude: -73.97567112),  // Atlantic Terminal
        "ADL": CLLocationCoordinate2D(latitude: 40.76144288, longitude: -73.78995927),  // Auburndale
        "BTA": CLLocationCoordinate2D(latitude: 40.70068942, longitude: -73.32405561),  // Babylon
        "BWN": CLLocationCoordinate2D(latitude: 40.65673224, longitude: -73.60716245),  // Baldwin
        "BSR": CLLocationCoordinate2D(latitude: 40.72443344, longitude: -73.25408295),  // Bay Shore
        "BSD": CLLocationCoordinate2D(latitude: 40.76315241, longitude: -73.77124986),  // Bayside
        "BRS": CLLocationCoordinate2D(latitude: 40.72220443, longitude: -73.71665289),  // Bellerose
        "BMR": CLLocationCoordinate2D(latitude: 40.66880043, longitude: -73.52886016),  // Bellmore
        "BPT": CLLocationCoordinate2D(latitude: 40.7737389, longitude: -72.94396574),   // Bellport
        "BRT": CLLocationCoordinate2D(latitude: 40.71368754, longitude: -73.72829722),  // Belmont Park
        "BPG": CLLocationCoordinate2D(latitude: 40.74303924, longitude: -73.48343821),  // Bethpage
        "BWD": CLLocationCoordinate2D(latitude: 40.78083474, longitude: -73.24361074),  // Brentwood
        "BHN": CLLocationCoordinate2D(latitude: 40.93898378, longitude: -72.31004593),  // Bridgehampton
        "BDY": CLLocationCoordinate2D(latitude: 40.76165318, longitude: -73.80176612),  // Broadway LIRR
        "CPL": CLLocationCoordinate2D(latitude: 40.74920704, longitude: -73.60365242),  // Carle Place
        "CHT": CLLocationCoordinate2D(latitude: 40.62217451, longitude: -73.72618275),  // Cedarhurst
        "CI": CLLocationCoordinate2D(latitude: 40.79185312, longitude: -73.19486082),   // Central Islip
        "CAV": CLLocationCoordinate2D(latitude: 40.64831835, longitude: -73.6639675),   // Centre Avenue
        "CSH": CLLocationCoordinate2D(latitude: 40.83563832, longitude: -73.45108591),  // Cold Spring Harbor
        "CPG": CLLocationCoordinate2D(latitude: 40.68101528, longitude: -73.39834027),  // Copiague
        "LCLP": CLLocationCoordinate2D(latitude: 40.72145656, longitude: -73.62967386),  // Country Life Press
        "DPK": CLLocationCoordinate2D(latitude: 40.76948364, longitude: -73.29356494),  // Deer Park
        "DGL": CLLocationCoordinate2D(latitude: 40.76806862, longitude: -73.74941265),  // Douglaston
        "EHN": CLLocationCoordinate2D(latitude: 40.96508629, longitude: -72.19324238),  // East Hampton
        "ENY": CLLocationCoordinate2D(latitude: 40.67581191, longitude: -73.90280882),  // East New York
        "ERY": CLLocationCoordinate2D(latitude: 40.64221085, longitude: -73.65821626),  // East Rockaway
        "EWN": CLLocationCoordinate2D(latitude: 40.7560191, longitude: -73.63940764),   // East Williston
        "EMT": CLLocationCoordinate2D(latitude: 40.720074, longitude: -73.725549),      // Elmont-UBS Arena
        "LFRY": CLLocationCoordinate2D(latitude: 40.60914311, longitude: -73.75054135),  // Far Rockaway
        "LFMD": CLLocationCoordinate2D(latitude: 40.73591503, longitude: -73.44123878),  // Farmingdale
        "FPK": CLLocationCoordinate2D(latitude: 40.72463725, longitude: -73.70639714),  // Floral Park
        "FLS": CLLocationCoordinate2D(latitude: 40.75789494, longitude: -73.83134684),  // Flushing Main Street
        "FHL": CLLocationCoordinate2D(latitude: 40.71957556, longitude: -73.84481402),  // Forest Hills
        "FPT": CLLocationCoordinate2D(latitude: 40.65745799, longitude: -73.58232401),  // Freeport
        "GCY": CLLocationCoordinate2D(latitude: 40.72310156, longitude: -73.64036107),  // Garden City
        "GBN": CLLocationCoordinate2D(latitude: 40.64925173, longitude: -73.70183483),  // Gibson
        "GCV": CLLocationCoordinate2D(latitude: 40.86583421, longitude: -73.61616614),  // Glen Cove
        "GHD": CLLocationCoordinate2D(latitude: 40.83222531, longitude: -73.62611822),  // Glen Head
        "GST": CLLocationCoordinate2D(latitude: 40.85798112, longitude: -73.62121715),  // Glen Street
        "GCT": CLLocationCoordinate2D(latitude: 40.752998, longitude: -73.977056),      // Grand Central Terminal (shared with MNR)
        "GNK": CLLocationCoordinate2D(latitude: 40.78721647, longitude: -73.72610046),  // Great Neck
        "GRV": CLLocationCoordinate2D(latitude: 40.74044444, longitude: -73.17019585),  // Great River
        "GWN": CLLocationCoordinate2D(latitude: 40.86866524, longitude: -73.36284977),  // Greenlawn
        "GPT": CLLocationCoordinate2D(latitude: 41.09970991, longitude: -72.36310396),  // Greenport
        "LGVL": CLLocationCoordinate2D(latitude: 40.81571566, longitude: -73.62687152),  // Greenvale
        "HBY": CLLocationCoordinate2D(latitude: 40.87660916, longitude: -72.52394936),  // Hampton Bays
        "HGN": CLLocationCoordinate2D(latitude: 40.69491356, longitude: -73.64620888),  // Hempstead Gardens
        "LHEM": CLLocationCoordinate2D(latitude: 40.71329663, longitude: -73.62503239),  // Hempstead
        "HWT": CLLocationCoordinate2D(latitude: 40.63676432, longitude: -73.70513866),  // Hewlett
        "LHVL": CLLocationCoordinate2D(latitude: 40.76717491, longitude: -73.52853322),  // Hicksville
        "LHOL": CLLocationCoordinate2D(latitude: 40.71018151, longitude: -73.76675252),  // Hollis
        "HPA": CLLocationCoordinate2D(latitude: 40.74239046, longitude: -73.94678997),  // Hunterspoint Avenue
        "LHUN": CLLocationCoordinate2D(latitude: 40.85300971, longitude: -73.40952576),  // Huntington
        "IWD": CLLocationCoordinate2D(latitude: 40.61228773, longitude: -73.74418354),  // Inwood
        "IPK": CLLocationCoordinate2D(latitude: 40.60129906, longitude: -73.65474248),  // Island Park
        "ISP": CLLocationCoordinate2D(latitude: 40.73583449, longitude: -73.20932145),  // Islip
        "JAM": CLLocationCoordinate2D(latitude: 40.69960817, longitude: -73.80852987),  // Jamaica
        "KGN": CLLocationCoordinate2D(latitude: 40.70964917, longitude: -73.83088807),  // Kew Gardens
        "KPK": CLLocationCoordinate2D(latitude: 40.88366659, longitude: -73.25624757),  // Kings Park
        "LLVW": CLLocationCoordinate2D(latitude: 40.68585582, longitude: -73.65213777),  // Lakeview
        "LTN": CLLocationCoordinate2D(latitude: 40.66848304, longitude: -73.75174687),  // Laurelton
        "LCE": CLLocationCoordinate2D(latitude: 40.6157347, longitude: -73.73589955),   // Lawrence
        "LHT": CLLocationCoordinate2D(latitude: 40.68826504, longitude: -73.36921149),  // Lindenhurst
        "LLNK": CLLocationCoordinate2D(latitude: 40.77504393, longitude: -73.74064662),  // Little Neck
        "LLMR": CLLocationCoordinate2D(latitude: 40.67513907, longitude: -73.76504303),  // Locust Manor
        "LVL": CLLocationCoordinate2D(latitude: 40.87446697, longitude: -73.59830284),  // Locust Valley
        "LBH": CLLocationCoordinate2D(latitude: 40.5901817, longitude: -73.66481822),   // Long Beach
        "LIC": CLLocationCoordinate2D(latitude: 40.74134343, longitude: -73.95763922),  // Long Island City
        "LYN": CLLocationCoordinate2D(latitude: 40.65605814, longitude: -73.67607083),  // Lynbrook
        "LMVN": CLLocationCoordinate2D(latitude: 40.67547844, longitude: -73.66886364),  // Malverne
        "MHT": CLLocationCoordinate2D(latitude: 40.7967241, longitude: -73.69989909),   // Manhasset
        "LMPK": CLLocationCoordinate2D(latitude: 40.6778591, longitude: -73.45473724),   // Massapequa Park
        "MQA": CLLocationCoordinate2D(latitude: 40.67693014, longitude: -73.46905552),  // Massapequa
        "MSY": CLLocationCoordinate2D(latitude: 40.79898815, longitude: -72.86442272),  // Mastic-Shirley
        "MAK": CLLocationCoordinate2D(latitude: 40.99179354, longitude: -72.53606243),  // Mattituck
        "MFD": CLLocationCoordinate2D(latitude: 40.81739665, longitude: -72.99890946),  // Medford
        "MAV": CLLocationCoordinate2D(latitude: 40.73516903, longitude: -73.66252148),  // Merillon Avenue
        "MRK": CLLocationCoordinate2D(latitude: 40.6638004, longitude: -73.55062102),   // Merrick
        "LSSM": CLLocationCoordinate2D(latitude: 40.75239835, longitude: -73.84370059),  // Mets-Willets Point
        "LMIN": CLLocationCoordinate2D(latitude: 40.74034743, longitude: -73.64086293),  // Mineola
        "MTK": CLLocationCoordinate2D(latitude: 41.04710896, longitude: -71.95388103),  // Montauk
        "LMHL": CLLocationCoordinate2D(latitude: 40.76270926, longitude: -73.81453928),  // Murray Hill LIRR
        "NBD": CLLocationCoordinate2D(latitude: 40.72296245, longitude: -73.66269823),  // Nassau Boulevard
        "NHP": CLLocationCoordinate2D(latitude: 40.73075708, longitude: -73.68095886),  // New Hyde Park
        "NPT": CLLocationCoordinate2D(latitude: 40.88064972, longitude: -73.32848513),  // Northport
        "NAV": CLLocationCoordinate2D(latitude: 40.67838785, longitude: -73.94822108),  // Nostrand Avenue
        "ODL": CLLocationCoordinate2D(latitude: 40.74343275, longitude: -73.13243549),  // Oakdale
        "ODE": CLLocationCoordinate2D(latitude: 40.63472102, longitude: -73.65466582),  // Oceanside
        "OBY": CLLocationCoordinate2D(latitude: 40.87533774, longitude: -73.53403366),  // Oyster Bay
        "PGE": CLLocationCoordinate2D(latitude: 40.76187901, longitude: -73.01574451),  // Patchogue
        "PLN": CLLocationCoordinate2D(latitude: 40.74535851, longitude: -73.39960092),  // Pinelawn
        "PDM": CLLocationCoordinate2D(latitude: 40.81069853, longitude: -73.69521438),  // Plandome
        "PJN": CLLocationCoordinate2D(latitude: 40.9345531, longitude: -73.05250164),   // Port Jefferson
        "PWS": CLLocationCoordinate2D(latitude: 40.82903533, longitude: -73.687401),    // Port Washington
        "QVG": CLLocationCoordinate2D(latitude: 40.71745785, longitude: -73.73645989),  // Queens Village
        "RHD": CLLocationCoordinate2D(latitude: 40.91983928, longitude: -72.66691054),  // Riverhead
        "RVC": CLLocationCoordinate2D(latitude: 40.65831811, longitude: -73.64654935),  // Rockville Centre
        "RON": CLLocationCoordinate2D(latitude: 40.80808613, longitude: -73.10594023),  // Ronkonkoma
        "ROS": CLLocationCoordinate2D(latitude: 40.66594933, longitude: -73.73554816),  // Rosedale
        "RSN": CLLocationCoordinate2D(latitude: 40.7904781, longitude: -73.64326175),   // Roslyn
        "SVL": CLLocationCoordinate2D(latitude: 40.74035373, longitude: -73.08645531),  // Sayville
        "SCF": CLLocationCoordinate2D(latitude: 40.85236805, longitude: -73.62541695),  // Sea Cliff
        "SFD": CLLocationCoordinate2D(latitude: 40.67572393, longitude: -73.48656847),  // Seaford
        "LSTN": CLLocationCoordinate2D(latitude: 40.85654755, longitude: -73.19803235),  // Smithtown
        "SHN": CLLocationCoordinate2D(latitude: 40.89471874, longitude: -72.39012376),  // Southampton
        "SHD": CLLocationCoordinate2D(latitude: 41.06632089, longitude: -72.4278803),   // Southold
        "LSPK": CLLocationCoordinate2D(latitude: 40.82131516, longitude: -72.70526225),  // Speonk
        "LSAB": CLLocationCoordinate2D(latitude: 40.69118348, longitude: -73.76550937),  // St. Albans
        "LSJM": CLLocationCoordinate2D(latitude: 40.88216931, longitude: -73.15950725),  // St. James
        "SMR": CLLocationCoordinate2D(latitude: 40.72302771, longitude: -73.68102041),  // Stewart Manor
        "LSBK": CLLocationCoordinate2D(latitude: 40.92032252, longitude: -73.12854943),   // Stony Brook
        "SYT": CLLocationCoordinate2D(latitude: 40.82485746, longitude: -73.5004456),   // Syosset
        "VSM": CLLocationCoordinate2D(latitude: 40.66151762, longitude: -73.70475875),  // Valley Stream
        "WGH": CLLocationCoordinate2D(latitude: 40.67299016, longitude: -73.50896484),  // Wantagh
        "WHD": CLLocationCoordinate2D(latitude: 40.70196099, longitude: -73.64164361),  // West Hempstead
        "WBY": CLLocationCoordinate2D(latitude: 40.75345386, longitude: -73.5858661),   // Westbury
        "WHN": CLLocationCoordinate2D(latitude: 40.83030532, longitude: -72.65032454),  // Westhampton
        "LWWD": CLLocationCoordinate2D(latitude: 40.66837227, longitude: -73.68120878),  // Westwood LIRR
        "WMR": CLLocationCoordinate2D(latitude: 40.63133646, longitude: -73.71371544),  // Woodmere
        "WDD": CLLocationCoordinate2D(latitude: 40.74585067, longitude: -73.90297516),  // Woodside
        "WYD": CLLocationCoordinate2D(latitude: 40.75480101, longitude: -73.35806588),  // Wyandanch
        "YPK": CLLocationCoordinate2D(latitude: 40.82561319, longitude: -72.91587848),  // Yaphank

        // Metro-North Railroad stations (GCT shared with LIRR above)
        "M125": CLLocationCoordinate2D(latitude: 40.805157, longitude: -73.939149),     // Harlem-125th Street
        "MEYS": CLLocationCoordinate2D(latitude: 40.8253, longitude: -73.9299),        // Yankees-E 153 St
        "MMRH": CLLocationCoordinate2D(latitude: 40.854252, longitude: -73.919583),    // Morris Heights
        "MUNH": CLLocationCoordinate2D(latitude: 40.862248, longitude: -73.91312),     // University Heights
        "MMBL": CLLocationCoordinate2D(latitude: 40.874333, longitude: -73.910941),    // Marble Hill
        "MSDV": CLLocationCoordinate2D(latitude: 40.878245, longitude: -73.921455),    // Spuyten Duyvil
        "MRVD": CLLocationCoordinate2D(latitude: 40.903981, longitude: -73.914126),    // Riverdale
        "MLUD": CLLocationCoordinate2D(latitude: 40.924972, longitude: -73.904612),    // Ludlow
        "MYON": CLLocationCoordinate2D(latitude: 40.935795, longitude: -73.902668),    // Yonkers
        "MGWD": CLLocationCoordinate2D(latitude: 40.950496, longitude: -73.899062),    // Glenwood
        "MGRY": CLLocationCoordinate2D(latitude: 40.972705, longitude: -73.889069),    // Greystone
        "MHOH": CLLocationCoordinate2D(latitude: 40.994109, longitude: -73.884512),    // Hastings-on-Hudson
        "MDBF": CLLocationCoordinate2D(latitude: 41.012459, longitude: -73.87949),     // Dobbs Ferry
        "MARD": CLLocationCoordinate2D(latitude: 41.026198, longitude: -73.876543),    // Ardsley-on-Hudson
        "MIRV": CLLocationCoordinate2D(latitude: 41.039993, longitude: -73.873083),    // Irvington
        "MTTN": CLLocationCoordinate2D(latitude: 41.076473, longitude: -73.864563),    // Tarrytown
        "MPHM": CLLocationCoordinate2D(latitude: 41.09492, longitude: -73.869755),     // Philipse Manor
        "MSCB": CLLocationCoordinate2D(latitude: 41.135763, longitude: -73.866163),    // Scarborough
        "MOSS": CLLocationCoordinate2D(latitude: 41.157663, longitude: -73.869281),    // Ossining
        "MCRH": CLLocationCoordinate2D(latitude: 41.189903, longitude: -73.882394),    // Croton-Harmon
        "MCRT": CLLocationCoordinate2D(latitude: 41.246259, longitude: -73.921884),    // Cortlandt
        "MPKS": CLLocationCoordinate2D(latitude: 41.285962, longitude: -73.93042),     // Peekskill
        "MMAN": CLLocationCoordinate2D(latitude: 41.332601, longitude: -73.970426),    // Manitou
        "MGAR": CLLocationCoordinate2D(latitude: 41.38178, longitude: -73.947202),     // Garrison
        "MCSP": CLLocationCoordinate2D(latitude: 41.415283, longitude: -73.95809),     // Cold Spring
        "MBRK": CLLocationCoordinate2D(latitude: 41.450181, longitude: -73.982449),    // Breakneck Ridge
        "MBCN": CLLocationCoordinate2D(latitude: 41.504007, longitude: -73.984528),    // Beacon
        "MNHB": CLLocationCoordinate2D(latitude: 41.587448, longitude: -73.947226),    // New Hamburg
        "MPOK": CLLocationCoordinate2D(latitude: 41.705839, longitude: -73.937946),    // Poughkeepsie
        "MMEL": CLLocationCoordinate2D(latitude: 40.825761, longitude: -73.915231),    // Melrose
        "MTRM": CLLocationCoordinate2D(latitude: 40.847301, longitude: -73.89955),     // Tremont
        "MFOR": CLLocationCoordinate2D(latitude: 40.8615, longitude: -73.89058),       // Fordham
        "MBOG": CLLocationCoordinate2D(latitude: 40.866555, longitude: -73.883109),    // Botanical Garden
        "MWBG": CLLocationCoordinate2D(latitude: 40.878569, longitude: -73.871064),    // Williams Bridge
        "MWDL": CLLocationCoordinate2D(latitude: 40.895361, longitude: -73.862916),    // Woodlawn
        "MWKF": CLLocationCoordinate2D(latitude: 40.905936, longitude: -73.85568),     // Wakefield
        "MMVW": CLLocationCoordinate2D(latitude: 40.912142, longitude: -73.851129),    // Mt Vernon West
        "MFLT": CLLocationCoordinate2D(latitude: 40.92699, longitude: -73.83948),      // Fleetwood
        "MBRX": CLLocationCoordinate2D(latitude: 40.93978, longitude: -73.835208),     // Bronxville
        "MTUC": CLLocationCoordinate2D(latitude: 40.949393, longitude: -73.830166),    // Tuckahoe
        "MCWD": CLLocationCoordinate2D(latitude: 40.958997, longitude: -73.820564),    // Crestwood
        "MSCD": CLLocationCoordinate2D(latitude: 40.989168, longitude: -73.808634),    // Scarsdale
        "MHSD": CLLocationCoordinate2D(latitude: 41.010333, longitude: -73.796407),    // Hartsdale
        "MWPL": CLLocationCoordinate2D(latitude: 41.032589, longitude: -73.775208),    // White Plains
        "MNWP": CLLocationCoordinate2D(latitude: 41.049806, longitude: -73.773142),    // North White Plains
        "MVAL": CLLocationCoordinate2D(latitude: 41.072819, longitude: -73.772599),    // Valhalla
        "MMTP": CLLocationCoordinate2D(latitude: 41.095877, longitude: -73.793822),    // Mt Pleasant
        "MHWT": CLLocationCoordinate2D(latitude: 41.108581, longitude: -73.79625),     // Hawthorne
        "MPLV": CLLocationCoordinate2D(latitude: 41.135222, longitude: -73.792661),    // Pleasantville
        "MCHP": CLLocationCoordinate2D(latitude: 41.158015, longitude: -73.774885),    // Chappaqua
        "MMTK": CLLocationCoordinate2D(latitude: 41.208242, longitude: -73.729778),    // Mt Kisco
        "MBDH": CLLocationCoordinate2D(latitude: 41.237316, longitude: -73.699936),    // Bedford Hills
        "MKAT": CLLocationCoordinate2D(latitude: 41.259552, longitude: -73.684155),    // Katonah
        "MGLD": CLLocationCoordinate2D(latitude: 41.294338, longitude: -73.677655),    // Goldens Bridge
        "MPRD": CLLocationCoordinate2D(latitude: 41.325775, longitude: -73.659061),    // Purdys
        "MCFL": CLLocationCoordinate2D(latitude: 41.347722, longitude: -73.662269),    // Croton Falls
        "MBRS": CLLocationCoordinate2D(latitude: 41.39447, longitude: -73.619802),     // Brewster
        "MSET": CLLocationCoordinate2D(latitude: 41.413203, longitude: -73.623787),    // Southeast
        "MPAT": CLLocationCoordinate2D(latitude: 41.511827, longitude: -73.604584),    // Patterson
        "MPAW": CLLocationCoordinate2D(latitude: 41.564205, longitude: -73.600524),    // Pawling
        "MAPT": CLLocationCoordinate2D(latitude: 41.592871, longitude: -73.588032),    // Appalachian Trail
        "MHVW": CLLocationCoordinate2D(latitude: 41.637525, longitude: -73.57145),     // Harlem Valley-Wingdale
        "MDVP": CLLocationCoordinate2D(latitude: 41.740401, longitude: -73.576502),    // Dover Plains
        "MTMR": CLLocationCoordinate2D(latitude: 41.779938, longitude: -73.558204),    // Tenmile River
        "MWAS": CLLocationCoordinate2D(latitude: 41.814722, longitude: -73.562197),    // Wassaic
        "MMVE": CLLocationCoordinate2D(latitude: 40.912161, longitude: -73.832185),    // Mt Vernon East
        "MPEL": CLLocationCoordinate2D(latitude: 40.910321, longitude: -73.810242),    // Pelham
        "MNRC": CLLocationCoordinate2D(latitude: 40.911605, longitude: -73.783807),    // New Rochelle
        "MLRM": CLLocationCoordinate2D(latitude: 40.933394, longitude: -73.759792),    // Larchmont
        "MMAM": CLLocationCoordinate2D(latitude: 40.954061, longitude: -73.736125),    // Mamaroneck
        "MHRR": CLLocationCoordinate2D(latitude: 40.969432, longitude: -73.712964),    // Harrison
        "MRYE": CLLocationCoordinate2D(latitude: 40.985922, longitude: -73.682553),    // Rye
        "MPCH": CLLocationCoordinate2D(latitude: 41.000732, longitude: -73.6647),      // Port Chester
        "MGRN": CLLocationCoordinate2D(latitude: 41.021277, longitude: -73.624621),    // Greenwich
        "MCOC": CLLocationCoordinate2D(latitude: 41.030171, longitude: -73.598306),    // Cos Cob
        "MRSD": CLLocationCoordinate2D(latitude: 41.031682, longitude: -73.588173),    // Riverside
        "MODG": CLLocationCoordinate2D(latitude: 41.033817, longitude: -73.565859),    // Old Greenwich
        "MSTM": CLLocationCoordinate2D(latitude: 41.046611, longitude: -73.542846),    // Stamford
        "MNOH": CLLocationCoordinate2D(latitude: 41.069041, longitude: -73.49788),     // Noroton Heights
        "MDAR": CLLocationCoordinate2D(latitude: 41.076913, longitude: -73.472966),    // Darien
        "MROW": CLLocationCoordinate2D(latitude: 41.077456, longitude: -73.445527),    // Rowayton
        "MSNW": CLLocationCoordinate2D(latitude: 41.09673, longitude: -73.421132),     // South Norwalk
        "MENW": CLLocationCoordinate2D(latitude: 41.103996, longitude: -73.404588),    // East Norwalk
        "MWPT": CLLocationCoordinate2D(latitude: 41.118928, longitude: -73.371413),    // Westport
        "MGRF": CLLocationCoordinate2D(latitude: 41.122265, longitude: -73.315408),    // Greens Farms
        "MSPT": CLLocationCoordinate2D(latitude: 41.134844, longitude: -73.28897),     // Southport
        "MFFD": CLLocationCoordinate2D(latitude: 41.143077, longitude: -73.257742),    // Fairfield
        "MFBR": CLLocationCoordinate2D(latitude: 41.161, longitude: -73.234336),       // Fairfield-Black Rock
        "MBGP": CLLocationCoordinate2D(latitude: 41.178677, longitude: -73.187076),    // Bridgeport
        "MSTR": CLLocationCoordinate2D(latitude: 41.194255, longitude: -73.131532),    // Stratford
        "MMIL": CLLocationCoordinate2D(latitude: 41.223231, longitude: -73.057647),    // Milford
        "MWHN": CLLocationCoordinate2D(latitude: 41.27142, longitude: -72.963488),     // West Haven
        "MNHV": CLLocationCoordinate2D(latitude: 41.296501, longitude: -72.92829),     // New Haven
        "MNSS": CLLocationCoordinate2D(latitude: 41.304979, longitude: -72.921747),    // New Haven-State St
        "MGLB": CLLocationCoordinate2D(latitude: 41.070547, longitude: -73.520021),    // Glenbrook
        "MSPD": CLLocationCoordinate2D(latitude: 41.08876, longitude: -73.517828),     // Springdale
        "MTMH": CLLocationCoordinate2D(latitude: 41.116012, longitude: -73.498149),    // Talmadge Hill
        "MNCA": CLLocationCoordinate2D(latitude: 41.146305, longitude: -73.495626),    // New Canaan
        "MMR7": CLLocationCoordinate2D(latitude: 41.146618, longitude: -73.427859),    // Merritt 7
        "MWIL": CLLocationCoordinate2D(latitude: 41.196202, longitude: -73.432434),    // Wilton
        "MCAN": CLLocationCoordinate2D(latitude: 41.21662, longitude: -73.426703),     // Cannondale
        "MBVL": CLLocationCoordinate2D(latitude: 41.26763, longitude: -73.441421),     // Branchville
        "MRED": CLLocationCoordinate2D(latitude: 41.325684, longitude: -73.4338),      // Redding
        "MBTH": CLLocationCoordinate2D(latitude: 41.376225, longitude: -73.418171),    // Bethel
        "MDBY": CLLocationCoordinate2D(latitude: 41.396146, longitude: -73.44879),     // Danbury
        "MDBS": CLLocationCoordinate2D(latitude: 41.319718, longitude: -73.083548),    // Derby-Shelton
        "MANS": CLLocationCoordinate2D(latitude: 41.344156, longitude: -73.079892),    // Ansonia
        "MSYM": CLLocationCoordinate2D(latitude: 41.395139, longitude: -73.072499),    // Seymour
        "MBCF": CLLocationCoordinate2D(latitude: 41.441752, longitude: -73.06359),     // Beacon Falls
        "MNAU": CLLocationCoordinate2D(latitude: 41.494204, longitude: -73.052655),    // Naugatuck
        "MWTB": CLLocationCoordinate2D(latitude: 41.552728, longitude: -73.046126),    // Waterbury

        // Amtrak/PATCO stations that previously collided with LIRR L-prefixed codes
        "CLP": CLLocationCoordinate2D(latitude: 38.4724, longitude: -77.9934),        // Culpeper, VA
        "FMD": CLLocationCoordinate2D(latitude: 40.6296, longitude: -91.3135),        // Fort Madison, IA
        "FRY": CLLocationCoordinate2D(latitude: 39.922572, longitude: -75.091805),    // Ferry Avenue (PATCO)
        "GVL": CLLocationCoordinate2D(latitude: 34.8526, longitude: -82.3940),        // Greenville, SC
        "HEM": CLLocationCoordinate2D(latitude: 38.7073, longitude: -91.4326),        // Hermann, MO
        "HOL": CLLocationCoordinate2D(latitude: 26.0116, longitude: -80.1679),        // Hollywood, FL
        "HUN": CLLocationCoordinate2D(latitude: 38.4158, longitude: -82.4397),        // Huntington, WV
        "HVL": CLLocationCoordinate2D(latitude: 34.8912, longitude: -76.9261),        // Havelock, NC
        "LMR": CLLocationCoordinate2D(latitude: 38.0896, longitude: -102.6186),       // Lamar, CO
        "LNK": CLLocationCoordinate2D(latitude: 40.8159, longitude: -96.7132),        // Lincoln, NE
        "LVW": CLLocationCoordinate2D(latitude: 32.4940, longitude: -94.7283),        // Longview, TX
        "MHL": CLLocationCoordinate2D(latitude: 32.5515, longitude: -94.3670),        // Marshall, TX
        "MIN": CLLocationCoordinate2D(latitude: 32.6620, longitude: -95.4891),        // Mineola, TX
        "MPK": CLLocationCoordinate2D(latitude: 34.2848, longitude: -118.8781),       // Moorpark, CA
        "MVN": CLLocationCoordinate2D(latitude: 34.3655, longitude: -92.8140),        // Malvern, AR
        "SAB": CLLocationCoordinate2D(latitude: 44.8124, longitude: -73.0862),        // St. Albans, VT
        "SJM": CLLocationCoordinate2D(latitude: 42.1091, longitude: -86.4845),        // St. Joseph, MI
        "SPK": CLLocationCoordinate2D(latitude: 47.6533, longitude: -117.4083),       // Spokane, WA
        "SSM": CLLocationCoordinate2D(latitude: 35.5328, longitude: -78.2801),        // Selma, NC
        "STN": CLLocationCoordinate2D(latitude: 48.3198, longitude: -102.3894),       // Stanley, ND
        "WWD": CLLocationCoordinate2D(latitude: 28.8662, longitude: -82.0395),         // Wildwood, FL

        // Metra (Chicago) stations
        "103RD-BEV": CLLocationCoordinate2D(latitude: 41.706111, longitude: -87.668889),  // 103rd St. - Beverly Hills
        "103RD-UP": CLLocationCoordinate2D(latitude: 41.706944, longitude: -87.607222),  // 103rd St. (Rosemoor)
        "107TH-BEV": CLLocationCoordinate2D(latitude: 41.698889, longitude: -87.67),  // 107th St. - Beverly Hills
        "107TH-UP": CLLocationCoordinate2D(latitude: 41.699722, longitude: -87.608889),  // 107th St.
        "111TH-BEV": CLLocationCoordinate2D(latitude: 41.692778, longitude: -87.670556),  // 111th St. - Morgan Park
        "111TH-UP": CLLocationCoordinate2D(latitude: 41.692778, longitude: -87.610556),  // 111th St. (Pullman)
        "115TH-BEV": CLLocationCoordinate2D(latitude: 41.685, longitude: -87.671667),  // 115th St. - Morgan Park
        "119TH-BEV": CLLocationCoordinate2D(latitude: 41.676389, longitude: -87.6725),  // 119th St.
        "123RD-BEV": CLLocationCoordinate2D(latitude: 41.67, longitude: -87.673611),  // 123rd St.
        "143RD-SWS": CLLocationCoordinate2D(latitude: 41.630556, longitude: -87.859167),  // Orland Park 143rd
        "147TH-UP": CLLocationCoordinate2D(latitude: 41.622778, longitude: -87.636111),  // 147th St.
        "153RD-SWS": CLLocationCoordinate2D(latitude: 41.609444, longitude: -87.873333),  // Orland Park 153rd
        "179TH-SWS": CLLocationCoordinate2D(latitude: 41.563889, longitude: -87.9025),  // Orland Park 179th
        "18TH-UP": CLLocationCoordinate2D(latitude: 41.858333, longitude: -87.618056),  // 18th St.
        "211TH-UP": CLLocationCoordinate2D(latitude: 41.506111, longitude: -87.698333),  // 211th St.
        "27TH-UP": CLLocationCoordinate2D(latitude: 41.844167, longitude: -87.613333),  // 27th St.
        "35TH": CLLocationCoordinate2D(latitude: 41.831389, longitude: -87.629167),  // 35th St. - Lou Jones
        "47TH-UP": CLLocationCoordinate2D(latitude: 41.809722, longitude: -87.591389),  // 47th St. (Kenwood)
        "51ST-53RD": CLLocationCoordinate2D(latitude: 41.8, longitude: -87.586944),  // 51st/53rd St. (Hyde Park)
        "55-56-57TH": CLLocationCoordinate2D(latitude: 41.793333, longitude: -87.5875),  // 55th - 56th - 57th St.
        "59TH-UP": CLLocationCoordinate2D(latitude: 41.788056, longitude: -87.588611),  // 59th St. (U. of Chicago)
        "63RD-UP": CLLocationCoordinate2D(latitude: 41.780278, longitude: -87.590556),  // 63rd St.
        "75TH-UP": CLLocationCoordinate2D(latitude: 41.758889, longitude: -87.595278),  // 75th St. (Grand Crossing)
        "79TH-SC": CLLocationCoordinate2D(latitude: 41.752222, longitude: -87.5525),  // Cheltenham (79th St.)
        "79TH-UP": CLLocationCoordinate2D(latitude: 41.750833, longitude: -87.597222),  // 79th St. (Chatham)
        "83RD-SC": CLLocationCoordinate2D(latitude: 41.745, longitude: -87.551667),  // 83rd St.
        "83RD-UP": CLLocationCoordinate2D(latitude: 41.744167, longitude: -87.598611),  // 83rd St. (Avalon Park)
        "87TH-SC": CLLocationCoordinate2D(latitude: 41.737778, longitude: -87.548333),  // 87th St.
        "87TH-UP": CLLocationCoordinate2D(latitude: 41.736944, longitude: -87.600278),  // 87th St. (Woodruff)
        "91ST-BEV": CLLocationCoordinate2D(latitude: 41.728056, longitude: -87.667222),  // 91st St. - Beverly Hills
        "91ST-UP": CLLocationCoordinate2D(latitude: 41.729444, longitude: -87.601944),  // 91st St.
        "93RD-SC": CLLocationCoordinate2D(latitude: 41.726667, longitude: -87.547778),  // South Chicago (93rd)
        "95TH-BEV": CLLocationCoordinate2D(latitude: 41.721389, longitude: -87.667222),  // 95th St. - Beverly Hills
        "95TH-UP": CLLocationCoordinate2D(latitude: 41.721944, longitude: -87.603889),  // 95th St.
        "99TH-BEV": CLLocationCoordinate2D(latitude: 41.713611, longitude: -87.6675),  // 99th St. - Beverly Hills
        "ANTIOCH": CLLocationCoordinate2D(latitude: 42.481111, longitude: -88.0925),  // Antioch
        "ARLINGTNHT": CLLocationCoordinate2D(latitude: 42.084167, longitude: -87.983611),  // Arlington Heights
        "ARLINGTNPK": CLLocationCoordinate2D(latitude: 42.095278, longitude: -88.009167),  // Arlington Park
        "ASHBURN": CLLocationCoordinate2D(latitude: 41.741667, longitude: -87.7125),  // Ashburn
        "ASHLAND": CLLocationCoordinate2D(latitude: 41.669444, longitude: -87.660556),  // Ashland
        "AURORA": CLLocationCoordinate2D(latitude: 41.760833, longitude: -88.308333),  // Aurora
        "BARRINGTON": CLLocationCoordinate2D(latitude: 42.152778, longitude: -88.131944),  // Barrington
        "BARTLETT": CLLocationCoordinate2D(latitude: 41.992222, longitude: -88.183889),  // Bartlett
        "BELLWOOD": CLLocationCoordinate2D(latitude: 41.891389, longitude: -87.8825),  // Bellwood
        "BELMONT": CLLocationCoordinate2D(latitude: 41.795278, longitude: -88.038056),  // Belmont
        "BENSENVIL": CLLocationCoordinate2D(latitude: 41.956944, longitude: -87.941944),  // Bensenville
        "BERKELEY": CLLocationCoordinate2D(latitude: 41.896111, longitude: -87.915278),  // Berkeley
        "BERWYN": CLLocationCoordinate2D(latitude: 41.833056, longitude: -87.793611),  // Berwyn
        "BIGTIMBER": CLLocationCoordinate2D(latitude: 42.058611, longitude: -88.327778),  // Big Timber
        "BLUEISLAND": CLLocationCoordinate2D(latitude: 41.656111, longitude: -87.675833),  // Blue Island
        "BNWESTERN": CLLocationCoordinate2D(latitude: 41.857778, longitude: -87.685278),  // Western Avenue
        "BRAESIDE": CLLocationCoordinate2D(latitude: 42.152778, longitude: -87.7725),  // Braeside
        "BRAINERD": CLLocationCoordinate2D(latitude: 41.732222, longitude: -87.658889),  // Brainerd
        "BROOKFIELD": CLLocationCoordinate2D(latitude: 41.821944, longitude: -87.843056),  // Brookfield
        "BRYNMAWR": CLLocationCoordinate2D(latitude: 41.766111, longitude: -87.576667),  // Bryn Mawr
        "BUFFGROVE": CLLocationCoordinate2D(latitude: 42.168611, longitude: -87.941389),  // Buffalo Grove
        "BURROAK": CLLocationCoordinate2D(latitude: 41.662222, longitude: -87.668889),  // Burr Oak
        "CALUMET": CLLocationCoordinate2D(latitude: 41.573611, longitude: -87.6625),  // Calumet
        "CARY": CLLocationCoordinate2D(latitude: 42.208889, longitude: -88.241389),  // Cary
        "CENTRALST": CLLocationCoordinate2D(latitude: 42.064167, longitude: -87.698056),  // Central St.
        "CHICRIDGE": CLLocationCoordinate2D(latitude: 41.703333, longitude: -87.780278),  // Chicago Ridge
        "CICERO": CLLocationCoordinate2D(latitude: 41.844167, longitude: -87.745556),  // Cicero
        "CLARNDNHIL": CLLocationCoordinate2D(latitude: 41.796944, longitude: -87.953611),  // Clarendon Hills
        "CLYBOURN": CLLocationCoordinate2D(latitude: 41.916944, longitude: -87.668056),  // Clybourn
        "COLLEGEAVE": CLLocationCoordinate2D(latitude: 41.868333, longitude: -88.090278),  // College Ave
        "CONGRESSPK": CLLocationCoordinate2D(latitude: 41.818889, longitude: -87.8575),  // Congress Park
        "CRYSTAL": CLLocationCoordinate2D(latitude: 42.244167, longitude: -88.317222),  // Crystal Lake
        "CUMBERLAND": CLLocationCoordinate2D(latitude: 42.0525, longitude: -87.912222),  // Cumberland
        "CUS": CLLocationCoordinate2D(latitude: 41.878889, longitude: -87.638889),  // Chicago Union Station
        "DEERFIELD": CLLocationCoordinate2D(latitude: 42.168056, longitude: -87.85),  // Deerfield
        "DEEROAD": CLLocationCoordinate2D(latitude: 42.024167, longitude: -87.856111),  // Dee Road
        "DESPLAINES": CLLocationCoordinate2D(latitude: 42.040833, longitude: -87.886667),  // Des Plaines
        "EDGEBROOK": CLLocationCoordinate2D(latitude: 41.997778, longitude: -87.765556),  // Edgebrook
        "EDISONPK": CLLocationCoordinate2D(latitude: 42.002222, longitude: -87.8175),  // Edison Park
        "ELBURN": CLLocationCoordinate2D(latitude: 41.890556, longitude: -88.463889),  // Elburn
        "ELGIN": CLLocationCoordinate2D(latitude: 42.036111, longitude: -88.286111),  // Elgin
        "ELMHURST": CLLocationCoordinate2D(latitude: 41.899722, longitude: -87.940833),  // Elmhurst
        "ELMWOODPK": CLLocationCoordinate2D(latitude: 41.924722, longitude: -87.814722),  // Elmwood Park
        "EVANSTON": CLLocationCoordinate2D(latitude: 42.048056, longitude: -87.684722),  // Evanston (Davis St.)
        "FAIRVIEWDG": CLLocationCoordinate2D(latitude: 41.795278, longitude: -87.993611),  // Fairview Ave.
        "FLOSSMOOR": CLLocationCoordinate2D(latitude: 41.543056, longitude: -87.678611),  // Flossmoor
        "FORESTGLEN": CLLocationCoordinate2D(latitude: 41.978056, longitude: -87.755556),  // Forest Glen
        "FOXLAKE": CLLocationCoordinate2D(latitude: 42.398333, longitude: -88.182222),  // Fox Lake
        "FOXRG": CLLocationCoordinate2D(latitude: 42.197778, longitude: -88.219444),  // Fox River Grove
        "FRANKLIN": CLLocationCoordinate2D(latitude: 41.936667, longitude: -87.866389),  // Franklin Park
        "FRANKLINPK": CLLocationCoordinate2D(latitude: 41.937778, longitude: -87.86),  // Franklin Pk
        "FTSHERIDAN": CLLocationCoordinate2D(latitude: 42.2175, longitude: -87.820833),  // Fort Sheridan
        "GALEWOOD": CLLocationCoordinate2D(latitude: 41.916389, longitude: -87.785833),  // Galewood
        "GENEVA": CLLocationCoordinate2D(latitude: 41.881667, longitude: -88.31),  // Geneva
        "GLADSTONEP": CLLocationCoordinate2D(latitude: 41.979722, longitude: -87.778056),  // Gladstone Park
        "GLENCOE": CLLocationCoordinate2D(latitude: 42.135556, longitude: -87.758056),  // Glencoe
        "GLENELLYN": CLLocationCoordinate2D(latitude: 41.876667, longitude: -88.064722),  // Glen Ellyn
        "GLENVIEW": CLLocationCoordinate2D(latitude: 42.075, longitude: -87.805556),  // Glenview
        "GOLF": CLLocationCoordinate2D(latitude: 42.058333, longitude: -87.796944),  // Golf
        "GRAND-CIC": CLLocationCoordinate2D(latitude: 41.914444, longitude: -87.746111),  // Grand/Cicero
        "GRAYLAND": CLLocationCoordinate2D(latitude: 41.948889, longitude: -87.740278),  // Grayland
        "GRAYSLAKE": CLLocationCoordinate2D(latitude: 42.333611, longitude: -88.043333),  // Grayslake
        "GRESHAM": CLLocationCoordinate2D(latitude: 41.736389, longitude: -87.644722),  // Gresham
        "GRTLAKES": CLLocationCoordinate2D(latitude: 42.306944, longitude: -87.846389),  // Great Lakes
        "HALSTED": CLLocationCoordinate2D(latitude: 41.860278, longitude: -87.647222),  // Halsted Street
        "HANOVERP": CLLocationCoordinate2D(latitude: 41.988056, longitude: -88.149167),  // Hanover Park
        "HANSONPK": CLLocationCoordinate2D(latitude: 41.916667, longitude: -87.766944),  // Hanson Park
        "HARLEM": CLLocationCoordinate2D(latitude: 41.831389, longitude: -87.801944),  // Harlem Ave.
        "HARVARD": CLLocationCoordinate2D(latitude: 42.419722, longitude: -88.6175),  // Harvard
        "HARVEY": CLLocationCoordinate2D(latitude: 41.608333, longitude: -87.643889),  // Harvey
        "HAZELCREST": CLLocationCoordinate2D(latitude: 41.580833, longitude: -87.658611),  // Hazel Crest
        "HEALY": CLLocationCoordinate2D(latitude: 41.924722, longitude: -87.727778),  // Healy
        "HICKORYCRK": CLLocationCoordinate2D(latitude: 41.548611, longitude: -87.845556),  // Hickory Creek
        "HIGHLANDPK": CLLocationCoordinate2D(latitude: 42.183333, longitude: -87.7975),  // Highland Park
        "HIGHLANDS": CLLocationCoordinate2D(latitude: 41.805, longitude: -87.918333),  // Highlands
        "HIGHWOOD": CLLocationCoordinate2D(latitude: 42.203333, longitude: -87.810556),  // Highwood
        "HINSDALE": CLLocationCoordinate2D(latitude: 41.802778, longitude: -87.928333),  // Hinsdale
        "HOLLYWOOD": CLLocationCoordinate2D(latitude: 41.824444, longitude: -87.833889),  // Hollywood
        "HOMEWOOD": CLLocationCoordinate2D(latitude: 41.562222, longitude: -87.668611),  // Homewood
        "HUBARDWOOD": CLLocationCoordinate2D(latitude: 42.118056, longitude: -87.743611),  // Hubbard Woods
        "INDIANHILL": CLLocationCoordinate2D(latitude: 42.094444, longitude: -87.723889),  // Indian Hill
        "INGLESIDE": CLLocationCoordinate2D(latitude: 42.383889, longitude: -88.153611),  // Ingleside
        "IRVINGPK": CLLocationCoordinate2D(latitude: 41.9525, longitude: -87.729722),  // Irving Park
        "ITASCA": CLLocationCoordinate2D(latitude: 41.971389, longitude: -88.014167),  // Itasca
        "IVANHOE": CLLocationCoordinate2D(latitude: 41.633333, longitude: -87.630278),  // Ivanhoe
        "JEFFERSONP": CLLocationCoordinate2D(latitude: 41.971389, longitude: -87.763333),  // Jefferson Park
        "JOLIET": CLLocationCoordinate2D(latitude: 41.524444, longitude: -88.079722),  // Joliet
        "KEDZIE": CLLocationCoordinate2D(latitude: 41.888333, longitude: -87.706944),  // Kedzie
        "KENILWORTH": CLLocationCoordinate2D(latitude: 42.086389, longitude: -87.716667),  // Kenilworth
        "KENOSHA": CLLocationCoordinate2D(latitude: 42.585833, longitude: -87.825833),  // Kenosha
        "KENSINGTN": CLLocationCoordinate2D(latitude: 41.685833, longitude: -87.612222),  // Kensington
        "LAFOX": CLLocationCoordinate2D(latitude: 41.886667, longitude: -88.412222),  // La Fox
        "LAGRANGE": CLLocationCoordinate2D(latitude: 41.815833, longitude: -87.871111),  // LaGrange Road
        "LAKEBLUFF": CLLocationCoordinate2D(latitude: 42.279722, longitude: -87.846667),  // Lake Bluff
        "LAKECOOKRD": CLLocationCoordinate2D(latitude: 42.151667, longitude: -87.841389),  // Lake-Cook
        "LAKEFRST": CLLocationCoordinate2D(latitude: 42.223611, longitude: -87.874722),  // Lake Forest
        "LAKEVILLA": CLLocationCoordinate2D(latitude: 42.4175, longitude: -88.079444),  // Lake Villa
        "LARAWAY": CLLocationCoordinate2D(latitude: 41.484722, longitude: -87.959722),  // Laraway Road
        "LAVERGNE": CLLocationCoordinate2D(latitude: 41.835556, longitude: -87.783333),  // Lavergne
        "LEMONT": CLLocationCoordinate2D(latitude: 41.673611, longitude: -88.0025),  // Lemont
        "LIBERTYVIL": CLLocationCoordinate2D(latitude: 42.291111, longitude: -87.956389),  // Libertyville
        "LISLE": CLLocationCoordinate2D(latitude: 41.797778, longitude: -88.071944),  // Lisle
        "LKFOREST": CLLocationCoordinate2D(latitude: 42.2525, longitude: -87.839722),  // Lake Forest.
        "LOCKPORT": CLLocationCoordinate2D(latitude: 41.585, longitude: -88.060278),  // Lockport
        "LOMBARD": CLLocationCoordinate2D(latitude: 41.886667, longitude: -88.018611),  // Lombard
        "LONGLAKE": CLLocationCoordinate2D(latitude: 42.368056, longitude: -88.128056),  // Long Lake
        "LONGWOOD": CLLocationCoordinate2D(latitude: 41.721111, longitude: -87.650278),  // 95th St.-Longwood
        "LSS": CLLocationCoordinate2D(latitude: 41.876389, longitude: -87.632222),  // LaSalle Street
        "MAINST": CLLocationCoordinate2D(latitude: 42.033333, longitude: -87.68),  // Main St.
        "MAINST-DG": CLLocationCoordinate2D(latitude: 41.795278, longitude: -88.009722),  // Downers Grove
        "MANHATTAN": CLLocationCoordinate2D(latitude: 41.418333, longitude: -87.989167),  // Manhattan
        "MANNHEIM": CLLocationCoordinate2D(latitude: 41.941667, longitude: -87.883333),  // Mannheim
        "MARS": CLLocationCoordinate2D(latitude: 41.919167, longitude: -87.794444),  // Mars
        "MATTESON": CLLocationCoordinate2D(latitude: 41.498611, longitude: -87.702222),  // Matteson
        "MAYFAIR": CLLocationCoordinate2D(latitude: 41.959722, longitude: -87.745833),  // Mayfair
        "MAYWOOD": CLLocationCoordinate2D(latitude: 41.888333, longitude: -87.838611),  // Maywood
        "MCCORMICK": CLLocationCoordinate2D(latitude: 41.851389, longitude: -87.616389),  // McCormick Place
        "MCHENRY": CLLocationCoordinate2D(latitude: 42.343333, longitude: -88.276111),  // McHenry
        "MEDINAH": CLLocationCoordinate2D(latitude: 41.978056, longitude: -88.050833),  // Medinah
        "MELROSEPK": CLLocationCoordinate2D(latitude: 41.890278, longitude: -87.855556),  // Melrose Park
        "MIDLOTHIAN": CLLocationCoordinate2D(latitude: 41.626389, longitude: -87.711667),  // Midlothian
        "MILLENNIUM": CLLocationCoordinate2D(latitude: 41.884167, longitude: -87.623056),  // Millennium Station
        "MOKENA": CLLocationCoordinate2D(latitude: 41.530833, longitude: -87.886667),  // Mokena
        "MONTCLARE": CLLocationCoordinate2D(latitude: 41.921667, longitude: -87.801667),  // Mont Clare
        "MORTONGRV": CLLocationCoordinate2D(latitude: 42.035, longitude: -87.785278),  // Morton Grove
        "MTPROSPECT": CLLocationCoordinate2D(latitude: 42.063056, longitude: -87.936111),  // Mt. Prospect
        "MUNDELEIN": CLLocationCoordinate2D(latitude: 42.266944, longitude: -87.998056),  // Mundelein
        "MUSEUM": CLLocationCoordinate2D(latitude: 41.868611, longitude: -87.621389),  // Museum Campus/11th St.
        "NAPERVILLE": CLLocationCoordinate2D(latitude: 41.779722, longitude: -88.145556),  // Naperville
        "NATIONALS": CLLocationCoordinate2D(latitude: 42.026389, longitude: -88.278889),  // National St
        "NBROOK": CLLocationCoordinate2D(latitude: 42.126944, longitude: -87.827778),  // Northbrook
        "NCHICAGO": CLLocationCoordinate2D(latitude: 42.328611, longitude: -87.836944),  // North Chicago
        "NCSGRAYSLK": CLLocationCoordinate2D(latitude: 42.359167, longitude: -88.050556),  // Washington St (Grayslake)
        "NEWLENOX": CLLocationCoordinate2D(latitude: 41.514444, longitude: -87.965278),  // New Lenox
        "NGLENVIEW": CLLocationCoordinate2D(latitude: 42.0975, longitude: -87.815833),  // Glen/N. Glenview
        "NORWOODP": CLLocationCoordinate2D(latitude: 41.991667, longitude: -87.798889),  // Norwood Park
        "OAKFOREST": CLLocationCoordinate2D(latitude: 41.604444, longitude: -87.738333),  // Oak Forest
        "OAKLAWN": CLLocationCoordinate2D(latitude: 41.719444, longitude: -87.748611),  // Oak Lawn Patriot
        "OAKPARK": CLLocationCoordinate2D(latitude: 41.886944, longitude: -87.801111),  // Oak Park
        "OHARE": CLLocationCoordinate2D(latitude: 41.995, longitude: -87.880556),  // O'Hare Transfer
        "OLYMPIA": CLLocationCoordinate2D(latitude: 41.521389, longitude: -87.69),  // Olympia Fields
        "OTC": CLLocationCoordinate2D(latitude: 41.882222, longitude: -87.640556),  // Chicago OTC
        "PALATINE": CLLocationCoordinate2D(latitude: 42.113056, longitude: -88.048333),  // Palatine
        "PALOSHTS": CLLocationCoordinate2D(latitude: 41.681944, longitude: -87.806944),  // Palos Heights
        "PALOSPARK": CLLocationCoordinate2D(latitude: 41.668889, longitude: -87.820278),  // Palos Park
        "PARKRIDGE": CLLocationCoordinate2D(latitude: 42.010278, longitude: -87.831667),  // Park Ridge
        "PETERSON": CLLocationCoordinate2D(latitude: 41.991111, longitude: -87.675),  // Peterson/Ridge
        "PINGREE": CLLocationCoordinate2D(latitude: 42.234167, longitude: -88.298056),  // Pingree Road
        "PRAIRCROSS": CLLocationCoordinate2D(latitude: 42.318056, longitude: -88.017222),  // Prairie Crossing.
        "PRAIRIEST": CLLocationCoordinate2D(latitude: 41.6625, longitude: -87.675),  // Prairie St.
        "PRAIRIEVW": CLLocationCoordinate2D(latitude: 42.198056, longitude: -87.955833),  // Prairie View
        "PRAIRIEXNG": CLLocationCoordinate2D(latitude: 42.320833, longitude: -88.015278),  // Prairie Crossing
        "PROSPECTHG": CLLocationCoordinate2D(latitude: 42.092222, longitude: -87.908056),  // Prospect Hts
        "RACINE": CLLocationCoordinate2D(latitude: 41.674167, longitude: -87.651944),  // Racine
        "RAVENSWOOD": CLLocationCoordinate2D(latitude: 41.968333, longitude: -87.674444),  // Ravenswood
        "RAVINIA": CLLocationCoordinate2D(latitude: 42.165, longitude: -87.782778),  // Ravinia
        "RAVINIAPK": CLLocationCoordinate2D(latitude: 42.158056, longitude: -87.776944),  // Ravinia Park
        "RICHTON": CLLocationCoordinate2D(latitude: 41.485556, longitude: -87.709444),  // Richton Park
        "RIVERDALE": CLLocationCoordinate2D(latitude: 41.646667, longitude: -87.623333),  // Riverdale
        "RIVERGROVE": CLLocationCoordinate2D(latitude: 41.931111, longitude: -87.836111),  // River Grove
        "RIVERSIDE": CLLocationCoordinate2D(latitude: 41.827222, longitude: -87.82),  // Riverside
        "RIVRFOREST": CLLocationCoordinate2D(latitude: 41.886944, longitude: -87.825),  // River Forest
        "ROBBINS": CLLocationCoordinate2D(latitude: 41.640833, longitude: -87.694444),  // Robbins
        "ROGERPK": CLLocationCoordinate2D(latitude: 42.009444, longitude: -87.675556),  // Rogers Park
        "ROMEOVILLE": CLLocationCoordinate2D(latitude: 41.637222, longitude: -88.049444),  // Romeoville
        "ROSELLE": CLLocationCoordinate2D(latitude: 41.981389, longitude: -88.067222),  // Roselle
        "ROSEMONT": CLLocationCoordinate2D(latitude: 41.976111, longitude: -87.873889),  // Rosemont
        "ROUNDLAKE": CLLocationCoordinate2D(latitude: 42.354444, longitude: -88.094167),  // Round Lake
        "ROUNDLKBCH": CLLocationCoordinate2D(latitude: 42.385, longitude: -88.065556),  // Round Lake Beach
        "ROUTE59": CLLocationCoordinate2D(latitude: 41.777778, longitude: -88.208611),  // Route 59
        "SCHAUM": CLLocationCoordinate2D(latitude: 41.989167, longitude: -88.118056),  // Schaumburg
        "SCHILLERPK": CLLocationCoordinate2D(latitude: 41.962778, longitude: -87.870556),  // Schiller Park
        "SOUTHSHORE": CLLocationCoordinate2D(latitude: 41.765278, longitude: -87.565833),  // South Shore
        "STATEST": CLLocationCoordinate2D(latitude: 41.674444, longitude: -87.621944),  // State St.
        "STEWARTRID": CLLocationCoordinate2D(latitude: 41.674444, longitude: -87.631667),  // Stewart Ridge
        "STONEAVE": CLLocationCoordinate2D(latitude: 41.814167, longitude: -87.878333),  // Stone Ave.
        "STONYISLND": CLLocationCoordinate2D(latitude: 41.766111, longitude: -87.586944),  // Stony Island
        "SUMMIT": CLLocationCoordinate2D(latitude: 41.795, longitude: -87.809722),  // Summit
        "TINLEY80TH": CLLocationCoordinate2D(latitude: 41.564444, longitude: -87.809444),  // Tinley-80th
        "TINLEYPARK": CLLocationCoordinate2D(latitude: 41.575833, longitude: -87.782778),  // Tinley Park
        "UNIVERSITY": CLLocationCoordinate2D(latitude: 41.459444, longitude: -87.723333),  // University Park
        "VANBUREN": CLLocationCoordinate2D(latitude: 41.876944, longitude: -87.623056),  // Van Buren St.
        "VERMONT": CLLocationCoordinate2D(latitude: 41.654722, longitude: -87.677778),  // Blue Island-Vermont
        "VERNON": CLLocationCoordinate2D(latitude: 42.215556, longitude: -87.964444),  // Vernon Hills
        "VILLAPARK": CLLocationCoordinate2D(latitude: 41.896389, longitude: -87.9775),  // Villa Park
        "WASHHGTS": CLLocationCoordinate2D(latitude: 41.705556, longitude: -87.655833),  // 103rd St.-Washington Hts.
        "WAUKEGAN": CLLocationCoordinate2D(latitude: 42.360556, longitude: -87.828333),  // Waukegan
        "WCHICAGO": CLLocationCoordinate2D(latitude: 41.881111, longitude: -88.198889),  // West Chicago
        "WESTERNAVE": CLLocationCoordinate2D(latitude: 41.889167, longitude: -87.688056),  // Western Ave
        "WESTMONT": CLLocationCoordinate2D(latitude: 41.795556, longitude: -87.976389),  // Westmont
        "WESTSPRING": CLLocationCoordinate2D(latitude: 41.808889, longitude: -87.901111),  // Western Springs
        "WHEATON": CLLocationCoordinate2D(latitude: 41.864444, longitude: -88.111944),  // Wheaton
        "WHEELING": CLLocationCoordinate2D(latitude: 42.136389, longitude: -87.927222),  // Wheeling
        "WHINSDALE": CLLocationCoordinate2D(latitude: 41.798889, longitude: -87.945278),  // West Hinsdale
        "WILLOWSPRN": CLLocationCoordinate2D(latitude: 41.733333, longitude: -87.878333),  // Willow Springs
        "WILMETTE": CLLocationCoordinate2D(latitude: 42.077222, longitude: -87.709167),  // Wilmette
        "WINDSORPK": CLLocationCoordinate2D(latitude: 41.758611, longitude: -87.559444),  // Windsor Park
        "WINFIELD": CLLocationCoordinate2D(latitude: 41.87, longitude: -88.156944),  // Winfield
        "WINNETKA": CLLocationCoordinate2D(latitude: 42.105278, longitude: -87.732778),  // Winnetka
        "WINTHROP": CLLocationCoordinate2D(latitude: 42.482778, longitude: -87.816111),  // Winthrop Harbor
        "WOODDALE": CLLocationCoordinate2D(latitude: 41.9625, longitude: -87.975278),  // Wood Dale
        "WOODSTOCK": CLLocationCoordinate2D(latitude: 42.316944, longitude: -88.4475),  // Woodstock
        "WORTH": CLLocationCoordinate2D(latitude: 41.691389, longitude: -87.795833),  // Worth
        "WPULLMAN": CLLocationCoordinate2D(latitude: 41.674167, longitude: -87.642222),  // West Pullman
        "WRIGHTWOOD": CLLocationCoordinate2D(latitude: 41.748889, longitude: -87.703611),  // Wrightwood
        "ZION": CLLocationCoordinate2D(latitude: 42.449167, longitude: -87.818056),  // Zion

        // NYC Subway Stations
    "S101": CLLocationCoordinate2D(latitude: 40.889248, longitude: -73.898583),
    "S103": CLLocationCoordinate2D(latitude: 40.884667, longitude: -73.90087),
    "S104": CLLocationCoordinate2D(latitude: 40.878856, longitude: -73.904834),
    "S106": CLLocationCoordinate2D(latitude: 40.874561, longitude: -73.909831),
    "S107": CLLocationCoordinate2D(latitude: 40.869444, longitude: -73.915279),
    "S108": CLLocationCoordinate2D(latitude: 40.864621, longitude: -73.918822),
    "S109": CLLocationCoordinate2D(latitude: 40.860531, longitude: -73.925536),
    "S110": CLLocationCoordinate2D(latitude: 40.855225, longitude: -73.929412),
    "S111": CLLocationCoordinate2D(latitude: 40.849505, longitude: -73.933596),
    "S112": CLLocationCoordinate2D(latitude: 40.840556, longitude: -73.940133),
    "S113": CLLocationCoordinate2D(latitude: 40.834041, longitude: -73.94489),
    "S114": CLLocationCoordinate2D(latitude: 40.826551, longitude: -73.95036),
    "S115": CLLocationCoordinate2D(latitude: 40.822008, longitude: -73.953676),
    "S116": CLLocationCoordinate2D(latitude: 40.815581, longitude: -73.958372),
    "S117": CLLocationCoordinate2D(latitude: 40.807722, longitude: -73.96411),
    "S118": CLLocationCoordinate2D(latitude: 40.803967, longitude: -73.966847),
    "S119": CLLocationCoordinate2D(latitude: 40.799446, longitude: -73.968379),
    "S120": CLLocationCoordinate2D(latitude: 40.793919, longitude: -73.972323),
    "S121": CLLocationCoordinate2D(latitude: 40.788644, longitude: -73.976218),
    "S122": CLLocationCoordinate2D(latitude: 40.783934, longitude: -73.979917),
    "S123": CLLocationCoordinate2D(latitude: 40.778453, longitude: -73.98197),
    "S124": CLLocationCoordinate2D(latitude: 40.77344, longitude: -73.982209),
    "S125": CLLocationCoordinate2D(latitude: 40.768247, longitude: -73.981929),
    "S126": CLLocationCoordinate2D(latitude: 40.761728, longitude: -73.983849),
    "S127": CLLocationCoordinate2D(latitude: 40.75529, longitude: -73.987495),
    "S128": CLLocationCoordinate2D(latitude: 40.750373, longitude: -73.991057),
    "S129": CLLocationCoordinate2D(latitude: 40.747215, longitude: -73.993365),
    "S130": CLLocationCoordinate2D(latitude: 40.744081, longitude: -73.995657),
    "S131": CLLocationCoordinate2D(latitude: 40.74104, longitude: -73.997871),
    "S132": CLLocationCoordinate2D(latitude: 40.737826, longitude: -74.000201),
    "S133": CLLocationCoordinate2D(latitude: 40.733422, longitude: -74.002906),
    "S134": CLLocationCoordinate2D(latitude: 40.728251, longitude: -74.005367),
    "S135": CLLocationCoordinate2D(latitude: 40.722854, longitude: -74.006277),
    "S136": CLLocationCoordinate2D(latitude: 40.719318, longitude: -74.006886),
    "S137": CLLocationCoordinate2D(latitude: 40.715478, longitude: -74.009266),
    "S138": CLLocationCoordinate2D(latitude: 40.711835, longitude: -74.012188),
    "S139": CLLocationCoordinate2D(latitude: 40.707513, longitude: -74.013783),
    "S142": CLLocationCoordinate2D(latitude: 40.702068, longitude: -74.013664),
    "S201": CLLocationCoordinate2D(latitude: 40.903125, longitude: -73.85062),
    "S204": CLLocationCoordinate2D(latitude: 40.898379, longitude: -73.854376),
    "S205": CLLocationCoordinate2D(latitude: 40.893193, longitude: -73.857473),
    "S206": CLLocationCoordinate2D(latitude: 40.888022, longitude: -73.860341),
    "S207": CLLocationCoordinate2D(latitude: 40.883895, longitude: -73.862633),
    "S208": CLLocationCoordinate2D(latitude: 40.87785, longitude: -73.866256),
    "S209": CLLocationCoordinate2D(latitude: 40.871356, longitude: -73.867164),
    "S210": CLLocationCoordinate2D(latitude: 40.865462, longitude: -73.867352),
    "S211": CLLocationCoordinate2D(latitude: 40.857192, longitude: -73.867615),
    "S212": CLLocationCoordinate2D(latitude: 40.848828, longitude: -73.868457),
    "S213": CLLocationCoordinate2D(latitude: 40.841894, longitude: -73.873488),
    "S214": CLLocationCoordinate2D(latitude: 40.840295, longitude: -73.880049),
    "S215": CLLocationCoordinate2D(latitude: 40.837288, longitude: -73.887734),
    "S216": CLLocationCoordinate2D(latitude: 40.829993, longitude: -73.891865),
    "S217": CLLocationCoordinate2D(latitude: 40.824073, longitude: -73.893064),
    "S218": CLLocationCoordinate2D(latitude: 40.822181, longitude: -73.896736),
    "S219": CLLocationCoordinate2D(latitude: 40.819585, longitude: -73.90177),
    "S220": CLLocationCoordinate2D(latitude: 40.81649, longitude: -73.907807),
    "S221": CLLocationCoordinate2D(latitude: 40.816109, longitude: -73.917757),
    "S222": CLLocationCoordinate2D(latitude: 40.81841, longitude: -73.926718),
    "S224": CLLocationCoordinate2D(latitude: 40.814229, longitude: -73.94077),
    "S225": CLLocationCoordinate2D(latitude: 40.807754, longitude: -73.945495),
    "S226": CLLocationCoordinate2D(latitude: 40.802098, longitude: -73.949625),
    "S227": CLLocationCoordinate2D(latitude: 40.799075, longitude: -73.951822),
    "S228": CLLocationCoordinate2D(latitude: 40.713051, longitude: -74.008811),
    "S229": CLLocationCoordinate2D(latitude: 40.709416, longitude: -74.006571),
    "S230": CLLocationCoordinate2D(latitude: 40.706821, longitude: -74.0091),
    "S231": CLLocationCoordinate2D(latitude: 40.697466, longitude: -73.993086),
    "S232": CLLocationCoordinate2D(latitude: 40.693219, longitude: -73.989998),
    "S233": CLLocationCoordinate2D(latitude: 40.690545, longitude: -73.985065),
    "S234": CLLocationCoordinate2D(latitude: 40.688246, longitude: -73.980492),
    "S235": CLLocationCoordinate2D(latitude: 40.684359, longitude: -73.977666),
    "S236": CLLocationCoordinate2D(latitude: 40.680829, longitude: -73.975098),
    "S237": CLLocationCoordinate2D(latitude: 40.675235, longitude: -73.971046),
    "S238": CLLocationCoordinate2D(latitude: 40.671987, longitude: -73.964375),
    "S239": CLLocationCoordinate2D(latitude: 40.670682, longitude: -73.958131),
    "S241": CLLocationCoordinate2D(latitude: 40.667883, longitude: -73.950683),
    "S242": CLLocationCoordinate2D(latitude: 40.662742, longitude: -73.95085),
    "S243": CLLocationCoordinate2D(latitude: 40.656652, longitude: -73.9502),
    "S244": CLLocationCoordinate2D(latitude: 40.650843, longitude: -73.949575),
    "S245": CLLocationCoordinate2D(latitude: 40.645098, longitude: -73.948959),
    "S246": CLLocationCoordinate2D(latitude: 40.639967, longitude: -73.948411),
    "S247": CLLocationCoordinate2D(latitude: 40.632836, longitude: -73.947642),
    "S248": CLLocationCoordinate2D(latitude: 40.669847, longitude: -73.950466),
    "S249": CLLocationCoordinate2D(latitude: 40.669399, longitude: -73.942161),
    "S250": CLLocationCoordinate2D(latitude: 40.668897, longitude: -73.932942),
    "S251": CLLocationCoordinate2D(latitude: 40.664717, longitude: -73.92261),
    "S252": CLLocationCoordinate2D(latitude: 40.661453, longitude: -73.916327),
    "S253": CLLocationCoordinate2D(latitude: 40.662549, longitude: -73.908946),
    "S254": CLLocationCoordinate2D(latitude: 40.663515, longitude: -73.902447),
    "S255": CLLocationCoordinate2D(latitude: 40.664635, longitude: -73.894895),
    "S256": CLLocationCoordinate2D(latitude: 40.665449, longitude: -73.889395),
    "S257": CLLocationCoordinate2D(latitude: 40.666235, longitude: -73.884079),
    "S301": CLLocationCoordinate2D(latitude: 40.82388, longitude: -73.93647),
    "S302": CLLocationCoordinate2D(latitude: 40.820421, longitude: -73.936245),
    "S401": CLLocationCoordinate2D(latitude: 40.886037, longitude: -73.878751),
    "S402": CLLocationCoordinate2D(latitude: 40.87975, longitude: -73.884655),
    "S405": CLLocationCoordinate2D(latitude: 40.873412, longitude: -73.890064),
    "S406": CLLocationCoordinate2D(latitude: 40.86776, longitude: -73.897174),
    "S407": CLLocationCoordinate2D(latitude: 40.862803, longitude: -73.901034),
    "S408": CLLocationCoordinate2D(latitude: 40.858407, longitude: -73.903879),
    "S409": CLLocationCoordinate2D(latitude: 40.853453, longitude: -73.907684),
    "S410": CLLocationCoordinate2D(latitude: 40.84848, longitude: -73.911794),
    "S411": CLLocationCoordinate2D(latitude: 40.844434, longitude: -73.914685),
    "S412": CLLocationCoordinate2D(latitude: 40.840075, longitude: -73.917791),
    "S413": CLLocationCoordinate2D(latitude: 40.835537, longitude: -73.9214),
    "S414": CLLocationCoordinate2D(latitude: 40.827994, longitude: -73.925831),
    "S415": CLLocationCoordinate2D(latitude: 40.818375, longitude: -73.927351),
    "S416": CLLocationCoordinate2D(latitude: 40.813224, longitude: -73.929849),
    "S418": CLLocationCoordinate2D(latitude: 40.710368, longitude: -74.009509),
    "S419": CLLocationCoordinate2D(latitude: 40.707557, longitude: -74.011862),
    "S420": CLLocationCoordinate2D(latitude: 40.704817, longitude: -74.014065),
    "S423": CLLocationCoordinate2D(latitude: 40.692404, longitude: -73.990151),
    "S501": CLLocationCoordinate2D(latitude: 40.8883, longitude: -73.830834),
    "S502": CLLocationCoordinate2D(latitude: 40.878663, longitude: -73.838591),
    "S503": CLLocationCoordinate2D(latitude: 40.869526, longitude: -73.846384),
    "S504": CLLocationCoordinate2D(latitude: 40.858985, longitude: -73.855359),
    "S505": CLLocationCoordinate2D(latitude: 40.854364, longitude: -73.860495),
    "S601": CLLocationCoordinate2D(latitude: 40.852462, longitude: -73.828121),
    "S602": CLLocationCoordinate2D(latitude: 40.84681, longitude: -73.832569),
    "S603": CLLocationCoordinate2D(latitude: 40.843863, longitude: -73.836322),
    "S604": CLLocationCoordinate2D(latitude: 40.839892, longitude: -73.842952),
    "S606": CLLocationCoordinate2D(latitude: 40.836488, longitude: -73.847036),
    "S607": CLLocationCoordinate2D(latitude: 40.834255, longitude: -73.851222),
    "S608": CLLocationCoordinate2D(latitude: 40.833226, longitude: -73.860816),
    "S609": CLLocationCoordinate2D(latitude: 40.831509, longitude: -73.867618),
    "S610": CLLocationCoordinate2D(latitude: 40.829521, longitude: -73.874516),
    "S611": CLLocationCoordinate2D(latitude: 40.828584, longitude: -73.879159),
    "S612": CLLocationCoordinate2D(latitude: 40.826525, longitude: -73.886283),
    "S613": CLLocationCoordinate2D(latitude: 40.820948, longitude: -73.890549),
    "S614": CLLocationCoordinate2D(latitude: 40.816104, longitude: -73.896435),
    "S615": CLLocationCoordinate2D(latitude: 40.812118, longitude: -73.904098),
    "S616": CLLocationCoordinate2D(latitude: 40.808719, longitude: -73.907657),
    "S617": CLLocationCoordinate2D(latitude: 40.805368, longitude: -73.914042),
    "S618": CLLocationCoordinate2D(latitude: 40.807566, longitude: -73.91924),
    "S619": CLLocationCoordinate2D(latitude: 40.810476, longitude: -73.926138),
    "S621": CLLocationCoordinate2D(latitude: 40.804138, longitude: -73.937594),
    "S622": CLLocationCoordinate2D(latitude: 40.798629, longitude: -73.941617),
    "S623": CLLocationCoordinate2D(latitude: 40.79502, longitude: -73.94425),
    "S624": CLLocationCoordinate2D(latitude: 40.7906, longitude: -73.947478),
    "S625": CLLocationCoordinate2D(latitude: 40.785672, longitude: -73.95107),
    "S626": CLLocationCoordinate2D(latitude: 40.779492, longitude: -73.955589),
    "S627": CLLocationCoordinate2D(latitude: 40.77362, longitude: -73.959874),
    "S628": CLLocationCoordinate2D(latitude: 40.768141, longitude: -73.96387),
    "S629": CLLocationCoordinate2D(latitude: 40.762526, longitude: -73.967967),
    "S630": CLLocationCoordinate2D(latitude: 40.757107, longitude: -73.97192),
    "S631": CLLocationCoordinate2D(latitude: 40.751776, longitude: -73.976848),
    "S632": CLLocationCoordinate2D(latitude: 40.746081, longitude: -73.982076),
    "S633": CLLocationCoordinate2D(latitude: 40.74307, longitude: -73.984264),
    "S634": CLLocationCoordinate2D(latitude: 40.739864, longitude: -73.986599),
    "S635": CLLocationCoordinate2D(latitude: 40.734673, longitude: -73.989951),
    "S636": CLLocationCoordinate2D(latitude: 40.730054, longitude: -73.99107),
    "S637": CLLocationCoordinate2D(latitude: 40.725915, longitude: -73.994659),
    "S638": CLLocationCoordinate2D(latitude: 40.722301, longitude: -73.997141),
    "S639": CLLocationCoordinate2D(latitude: 40.718803, longitude: -74.000193),
    "S640": CLLocationCoordinate2D(latitude: 40.713065, longitude: -74.004131),
    "S701": CLLocationCoordinate2D(latitude: 40.7596, longitude: -73.83003),
    "S702": CLLocationCoordinate2D(latitude: 40.754622, longitude: -73.845625),
    "S705": CLLocationCoordinate2D(latitude: 40.75173, longitude: -73.855334),
    "S706": CLLocationCoordinate2D(latitude: 40.749865, longitude: -73.8627),
    "S707": CLLocationCoordinate2D(latitude: 40.749145, longitude: -73.869527),
    "S708": CLLocationCoordinate2D(latitude: 40.748408, longitude: -73.876613),
    "S709": CLLocationCoordinate2D(latitude: 40.747659, longitude: -73.883697),
    "S710": CLLocationCoordinate2D(latitude: 40.746848, longitude: -73.891394),
    "S711": CLLocationCoordinate2D(latitude: 40.746325, longitude: -73.896403),
    "S712": CLLocationCoordinate2D(latitude: 40.74563, longitude: -73.902984),
    "S713": CLLocationCoordinate2D(latitude: 40.744149, longitude: -73.912549),
    "S714": CLLocationCoordinate2D(latitude: 40.743132, longitude: -73.918435),
    "S715": CLLocationCoordinate2D(latitude: 40.743781, longitude: -73.924016),
    "S716": CLLocationCoordinate2D(latitude: 40.744587, longitude: -73.930997),
    "S718": CLLocationCoordinate2D(latitude: 40.750582, longitude: -73.940202),
    "S719": CLLocationCoordinate2D(latitude: 40.747023, longitude: -73.945264),
    "S720": CLLocationCoordinate2D(latitude: 40.742216, longitude: -73.948916),
    "S721": CLLocationCoordinate2D(latitude: 40.742626, longitude: -73.953581),
    "S723": CLLocationCoordinate2D(latitude: 40.751431, longitude: -73.976041),
    "S724": CLLocationCoordinate2D(latitude: 40.753821, longitude: -73.981963),
    "S725": CLLocationCoordinate2D(latitude: 40.755477, longitude: -73.987691),
    "S726": CLLocationCoordinate2D(latitude: 40.755882, longitude: -74.00191),
    "S901": CLLocationCoordinate2D(latitude: 40.752769, longitude: -73.979189),
    "S902": CLLocationCoordinate2D(latitude: 40.755983, longitude: -73.986229),
    "SA02": CLLocationCoordinate2D(latitude: 40.868072, longitude: -73.919899),
    "SA03": CLLocationCoordinate2D(latitude: 40.865491, longitude: -73.927271),
    "SA05": CLLocationCoordinate2D(latitude: 40.859022, longitude: -73.93418),
    "SA06": CLLocationCoordinate2D(latitude: 40.851695, longitude: -73.937969),
    "SA07": CLLocationCoordinate2D(latitude: 40.847391, longitude: -73.939704),
    "SA09": CLLocationCoordinate2D(latitude: 40.840719, longitude: -73.939561),
    "SA10": CLLocationCoordinate2D(latitude: 40.836013, longitude: -73.939892),
    "SA11": CLLocationCoordinate2D(latitude: 40.830518, longitude: -73.941514),
    "SA12": CLLocationCoordinate2D(latitude: 40.824783, longitude: -73.944216),
    "SA14": CLLocationCoordinate2D(latitude: 40.817894, longitude: -73.947649),
    "SA15": CLLocationCoordinate2D(latitude: 40.811109, longitude: -73.952343),
    "SA16": CLLocationCoordinate2D(latitude: 40.805085, longitude: -73.954882),
    "SA17": CLLocationCoordinate2D(latitude: 40.800603, longitude: -73.958161),
    "SA18": CLLocationCoordinate2D(latitude: 40.796092, longitude: -73.961454),
    "SA19": CLLocationCoordinate2D(latitude: 40.791642, longitude: -73.964696),
    "SA20": CLLocationCoordinate2D(latitude: 40.785868, longitude: -73.968916),
    "SA21": CLLocationCoordinate2D(latitude: 40.781433, longitude: -73.972143),
    "SA22": CLLocationCoordinate2D(latitude: 40.775594, longitude: -73.97641),
    "SA24": CLLocationCoordinate2D(latitude: 40.768296, longitude: -73.981736),
    "SA25": CLLocationCoordinate2D(latitude: 40.762456, longitude: -73.985984),
    "SA27": CLLocationCoordinate2D(latitude: 40.757308, longitude: -73.989735),
    "SA28": CLLocationCoordinate2D(latitude: 40.752287, longitude: -73.993391),
    "SA30": CLLocationCoordinate2D(latitude: 40.745906, longitude: -73.998041),
    "SA31": CLLocationCoordinate2D(latitude: 40.740893, longitude: -74.00169),
    "SA32": CLLocationCoordinate2D(latitude: 40.732338, longitude: -74.000495),
    "SA33": CLLocationCoordinate2D(latitude: 40.726227, longitude: -74.003739),
    "SA34": CLLocationCoordinate2D(latitude: 40.720824, longitude: -74.005229),
    "SA36": CLLocationCoordinate2D(latitude: 40.714111, longitude: -74.008585),
    "SA38": CLLocationCoordinate2D(latitude: 40.710197, longitude: -74.007691),
    "SA40": CLLocationCoordinate2D(latitude: 40.699337, longitude: -73.990531),
    "SA41": CLLocationCoordinate2D(latitude: 40.692338, longitude: -73.987342),
    "SA42": CLLocationCoordinate2D(latitude: 40.688484, longitude: -73.985001),
    "SA43": CLLocationCoordinate2D(latitude: 40.686113, longitude: -73.973946),
    "SA44": CLLocationCoordinate2D(latitude: 40.683263, longitude: -73.965838),
    "SA45": CLLocationCoordinate2D(latitude: 40.68138, longitude: -73.956848),
    "SA46": CLLocationCoordinate2D(latitude: 40.680438, longitude: -73.950426),
    "SA47": CLLocationCoordinate2D(latitude: 40.679921, longitude: -73.940858),
    "SA48": CLLocationCoordinate2D(latitude: 40.679364, longitude: -73.930729),
    "SA49": CLLocationCoordinate2D(latitude: 40.678822, longitude: -73.920786),
    "SA50": CLLocationCoordinate2D(latitude: 40.67834, longitude: -73.911946),
    "SA51": CLLocationCoordinate2D(latitude: 40.678334, longitude: -73.905316),
    "SA52": CLLocationCoordinate2D(latitude: 40.674542, longitude: -73.896548),
    "SA53": CLLocationCoordinate2D(latitude: 40.67271, longitude: -73.890358),
    "SA54": CLLocationCoordinate2D(latitude: 40.67413, longitude: -73.88075),
    "SA55": CLLocationCoordinate2D(latitude: 40.675377, longitude: -73.872106),
    "SA57": CLLocationCoordinate2D(latitude: 40.677044, longitude: -73.86505),
    "SA59": CLLocationCoordinate2D(latitude: 40.679371, longitude: -73.858992),
    "SA60": CLLocationCoordinate2D(latitude: 40.679843, longitude: -73.85147),
    "SA61": CLLocationCoordinate2D(latitude: 40.680429, longitude: -73.843853),
    "SA63": CLLocationCoordinate2D(latitude: 40.681711, longitude: -73.837683),
    "SA64": CLLocationCoordinate2D(latitude: 40.684331, longitude: -73.832163),
    "SA65": CLLocationCoordinate2D(latitude: 40.685951, longitude: -73.825798),
    "SB04": CLLocationCoordinate2D(latitude: 40.754203, longitude: -73.942836),
    "SB06": CLLocationCoordinate2D(latitude: 40.759145, longitude: -73.95326),
    "SB08": CLLocationCoordinate2D(latitude: 40.764629, longitude: -73.966113),
    "SB10": CLLocationCoordinate2D(latitude: 40.763972, longitude: -73.97745),
    "SB12": CLLocationCoordinate2D(latitude: 40.646292, longitude: -73.994324),
    "SB13": CLLocationCoordinate2D(latitude: 40.640914, longitude: -73.994304),
    "SB14": CLLocationCoordinate2D(latitude: 40.63626, longitude: -73.994791),
    "SB15": CLLocationCoordinate2D(latitude: 40.631435, longitude: -73.995476),
    "SB16": CLLocationCoordinate2D(latitude: 40.626472, longitude: -73.996895),
    "SB17": CLLocationCoordinate2D(latitude: 40.619589, longitude: -73.998864),
    "SB18": CLLocationCoordinate2D(latitude: 40.613501, longitude: -74.00061),
    "SB19": CLLocationCoordinate2D(latitude: 40.607954, longitude: -74.001736),
    "SB20": CLLocationCoordinate2D(latitude: 40.604556, longitude: -73.998168),
    "SB21": CLLocationCoordinate2D(latitude: 40.601875, longitude: -73.993728),
    "SB22": CLLocationCoordinate2D(latitude: 40.597704, longitude: -73.986829),
    "SB23": CLLocationCoordinate2D(latitude: 40.588841, longitude: -73.983765),
    "SD01": CLLocationCoordinate2D(latitude: 40.874811, longitude: -73.878855),
    "SD03": CLLocationCoordinate2D(latitude: 40.873244, longitude: -73.887138),
    "SD04": CLLocationCoordinate2D(latitude: 40.866978, longitude: -73.893509),
    "SD05": CLLocationCoordinate2D(latitude: 40.861296, longitude: -73.897749),
    "SD06": CLLocationCoordinate2D(latitude: 40.856093, longitude: -73.900741),
    "SD07": CLLocationCoordinate2D(latitude: 40.85041, longitude: -73.905227),
    "SD08": CLLocationCoordinate2D(latitude: 40.8459, longitude: -73.910136),
    "SD09": CLLocationCoordinate2D(latitude: 40.839306, longitude: -73.9134),
    "SD10": CLLocationCoordinate2D(latitude: 40.833771, longitude: -73.91844),
    "SD11": CLLocationCoordinate2D(latitude: 40.827905, longitude: -73.925651),
    "SD12": CLLocationCoordinate2D(latitude: 40.830135, longitude: -73.938209),
    "SD13": CLLocationCoordinate2D(latitude: 40.824783, longitude: -73.944216),
    "SD14": CLLocationCoordinate2D(latitude: 40.762862, longitude: -73.981637),
    "SD15": CLLocationCoordinate2D(latitude: 40.758663, longitude: -73.981329),
    "SD16": CLLocationCoordinate2D(latitude: 40.754222, longitude: -73.984569),
    "SD17": CLLocationCoordinate2D(latitude: 40.749719, longitude: -73.987823),
    "SD18": CLLocationCoordinate2D(latitude: 40.742878, longitude: -73.992821),
    "SD19": CLLocationCoordinate2D(latitude: 40.738228, longitude: -73.996209),
    "SD20": CLLocationCoordinate2D(latitude: 40.732338, longitude: -74.000495),
    "SD21": CLLocationCoordinate2D(latitude: 40.725297, longitude: -73.996204),
    "SD22": CLLocationCoordinate2D(latitude: 40.718267, longitude: -73.993753),
    "SD24": CLLocationCoordinate2D(latitude: 40.68446, longitude: -73.97689),
    "SD25": CLLocationCoordinate2D(latitude: 40.67705, longitude: -73.972367),
    "SD26": CLLocationCoordinate2D(latitude: 40.661614, longitude: -73.962246),
    "SD27": CLLocationCoordinate2D(latitude: 40.655292, longitude: -73.961495),
    "SD28": CLLocationCoordinate2D(latitude: 40.650527, longitude: -73.962982),
    "SD29": CLLocationCoordinate2D(latitude: 40.644031, longitude: -73.964492),
    "SD30": CLLocationCoordinate2D(latitude: 40.640927, longitude: -73.963891),
    "SD31": CLLocationCoordinate2D(latitude: 40.635082, longitude: -73.962793),
    "SD32": CLLocationCoordinate2D(latitude: 40.62927, longitude: -73.961639),
    "SD33": CLLocationCoordinate2D(latitude: 40.625039, longitude: -73.960803),
    "SD34": CLLocationCoordinate2D(latitude: 40.617618, longitude: -73.959399),
    "SD35": CLLocationCoordinate2D(latitude: 40.60867, longitude: -73.957734),
    "SD37": CLLocationCoordinate2D(latitude: 40.5993, longitude: -73.955929),
    "SD38": CLLocationCoordinate2D(latitude: 40.595246, longitude: -73.955161),
    "SD39": CLLocationCoordinate2D(latitude: 40.586896, longitude: -73.954155),
    "SD40": CLLocationCoordinate2D(latitude: 40.577621, longitude: -73.961376),
    "SD41": CLLocationCoordinate2D(latitude: 40.576312, longitude: -73.968501),
    "SD42": CLLocationCoordinate2D(latitude: 40.576127, longitude: -73.975939),
    "SD43": CLLocationCoordinate2D(latitude: 40.577422, longitude: -73.981233),
    "SE01": CLLocationCoordinate2D(latitude: 40.712582, longitude: -74.009781),
    "SF01": CLLocationCoordinate2D(latitude: 40.712646, longitude: -73.783817),
    "SF02": CLLocationCoordinate2D(latitude: 40.71047, longitude: -73.793604),
    "SF03": CLLocationCoordinate2D(latitude: 40.707564, longitude: -73.803326),
    "SF04": CLLocationCoordinate2D(latitude: 40.70546, longitude: -73.810708),
    "SF05": CLLocationCoordinate2D(latitude: 40.709179, longitude: -73.820574),
    "SF06": CLLocationCoordinate2D(latitude: 40.714441, longitude: -73.831008),
    "SF07": CLLocationCoordinate2D(latitude: 40.718331, longitude: -73.837324),
    "SF09": CLLocationCoordinate2D(latitude: 40.747846, longitude: -73.946),
    "SF11": CLLocationCoordinate2D(latitude: 40.757552, longitude: -73.969055),
    "SF12": CLLocationCoordinate2D(latitude: 40.760167, longitude: -73.975224),
    "SF14": CLLocationCoordinate2D(latitude: 40.723402, longitude: -73.989938),
    "SF15": CLLocationCoordinate2D(latitude: 40.718611, longitude: -73.988114),
    "SF16": CLLocationCoordinate2D(latitude: 40.713715, longitude: -73.990173),
    "SF18": CLLocationCoordinate2D(latitude: 40.701397, longitude: -73.986751),
    "SF20": CLLocationCoordinate2D(latitude: 40.686145, longitude: -73.990862),
    "SF21": CLLocationCoordinate2D(latitude: 40.680303, longitude: -73.995048),
    "SF22": CLLocationCoordinate2D(latitude: 40.67358, longitude: -73.995959),
    "SF23": CLLocationCoordinate2D(latitude: 40.670272, longitude: -73.989779),
    "SF24": CLLocationCoordinate2D(latitude: 40.666271, longitude: -73.980305),
    "SF25": CLLocationCoordinate2D(latitude: 40.660365, longitude: -73.979493),
    "SF26": CLLocationCoordinate2D(latitude: 40.650782, longitude: -73.975776),
    "SF27": CLLocationCoordinate2D(latitude: 40.644041, longitude: -73.979678),
    "SF29": CLLocationCoordinate2D(latitude: 40.636119, longitude: -73.978172),
    "SF30": CLLocationCoordinate2D(latitude: 40.629755, longitude: -73.976971),
    "SF31": CLLocationCoordinate2D(latitude: 40.625322, longitude: -73.976127),
    "SF32": CLLocationCoordinate2D(latitude: 40.620769, longitude: -73.975264),
    "SF33": CLLocationCoordinate2D(latitude: 40.61514, longitude: -73.974197),
    "SF34": CLLocationCoordinate2D(latitude: 40.608944, longitude: -73.973022),
    "SF35": CLLocationCoordinate2D(latitude: 40.603217, longitude: -73.972361),
    "SF36": CLLocationCoordinate2D(latitude: 40.596063, longitude: -73.973357),
    "SF38": CLLocationCoordinate2D(latitude: 40.58962, longitude: -73.97425),
    "SF39": CLLocationCoordinate2D(latitude: 40.581011, longitude: -73.974574),
    "SG05": CLLocationCoordinate2D(latitude: 40.702147, longitude: -73.801109),
    "SG06": CLLocationCoordinate2D(latitude: 40.700486, longitude: -73.807969),
    "SG07": CLLocationCoordinate2D(latitude: 40.702566, longitude: -73.816859),
    "SG08": CLLocationCoordinate2D(latitude: 40.721691, longitude: -73.844521),
    "SG09": CLLocationCoordinate2D(latitude: 40.726523, longitude: -73.852719),
    "SG10": CLLocationCoordinate2D(latitude: 40.729846, longitude: -73.861604),
    "SG11": CLLocationCoordinate2D(latitude: 40.733106, longitude: -73.869229),
    "SG12": CLLocationCoordinate2D(latitude: 40.737015, longitude: -73.877223),
    "SG13": CLLocationCoordinate2D(latitude: 40.742454, longitude: -73.882017),
    "SG14": CLLocationCoordinate2D(latitude: 40.746644, longitude: -73.891338),
    "SG15": CLLocationCoordinate2D(latitude: 40.749669, longitude: -73.898453),
    "SG16": CLLocationCoordinate2D(latitude: 40.752885, longitude: -73.906006),
    "SG18": CLLocationCoordinate2D(latitude: 40.756312, longitude: -73.913333),
    "SG19": CLLocationCoordinate2D(latitude: 40.756879, longitude: -73.92074),
    "SG20": CLLocationCoordinate2D(latitude: 40.752039, longitude: -73.928781),
    "SG21": CLLocationCoordinate2D(latitude: 40.748973, longitude: -73.937243),
    "SG22": CLLocationCoordinate2D(latitude: 40.746554, longitude: -73.943832),
    "SG24": CLLocationCoordinate2D(latitude: 40.744065, longitude: -73.949724),
    "SG26": CLLocationCoordinate2D(latitude: 40.731352, longitude: -73.954449),
    "SG28": CLLocationCoordinate2D(latitude: 40.724635, longitude: -73.951277),
    "SG29": CLLocationCoordinate2D(latitude: 40.712792, longitude: -73.951418),
    "SG30": CLLocationCoordinate2D(latitude: 40.706092, longitude: -73.950308),
    "SG31": CLLocationCoordinate2D(latitude: 40.700377, longitude: -73.950234),
    "SG32": CLLocationCoordinate2D(latitude: 40.694568, longitude: -73.949046),
    "SG33": CLLocationCoordinate2D(latitude: 40.689627, longitude: -73.953522),
    "SG34": CLLocationCoordinate2D(latitude: 40.688873, longitude: -73.96007),
    "SG35": CLLocationCoordinate2D(latitude: 40.688089, longitude: -73.966839),
    "SG36": CLLocationCoordinate2D(latitude: 40.687119, longitude: -73.975375),
    "SH01": CLLocationCoordinate2D(latitude: 40.672097, longitude: -73.835919),
    "SH02": CLLocationCoordinate2D(latitude: 40.668234, longitude: -73.834058),
    "SH03": CLLocationCoordinate2D(latitude: 40.660476, longitude: -73.830301),
    "SH04": CLLocationCoordinate2D(latitude: 40.608382, longitude: -73.815925),
    "SH06": CLLocationCoordinate2D(latitude: 40.590927, longitude: -73.796924),
    "SH07": CLLocationCoordinate2D(latitude: 40.592374, longitude: -73.788522),
    "SH08": CLLocationCoordinate2D(latitude: 40.592943, longitude: -73.776013),
    "SH09": CLLocationCoordinate2D(latitude: 40.595398, longitude: -73.768175),
    "SH10": CLLocationCoordinate2D(latitude: 40.600066, longitude: -73.761353),
    "SH11": CLLocationCoordinate2D(latitude: 40.603995, longitude: -73.755405),
    "SH12": CLLocationCoordinate2D(latitude: 40.588034, longitude: -73.813641),
    "SH13": CLLocationCoordinate2D(latitude: 40.585307, longitude: -73.820558),
    "SH14": CLLocationCoordinate2D(latitude: 40.583209, longitude: -73.827559),
    "SH15": CLLocationCoordinate2D(latitude: 40.580903, longitude: -73.835592),
    "SJ12": CLLocationCoordinate2D(latitude: 40.700492, longitude: -73.828294),
    "SJ13": CLLocationCoordinate2D(latitude: 40.697418, longitude: -73.836345),
    "SJ14": CLLocationCoordinate2D(latitude: 40.695178, longitude: -73.84433),
    "SJ15": CLLocationCoordinate2D(latitude: 40.693879, longitude: -73.851576),
    "SJ16": CLLocationCoordinate2D(latitude: 40.692435, longitude: -73.86001),
    "SJ17": CLLocationCoordinate2D(latitude: 40.691324, longitude: -73.867139),
    "SJ19": CLLocationCoordinate2D(latitude: 40.689941, longitude: -73.87255),
    "SJ20": CLLocationCoordinate2D(latitude: 40.683194, longitude: -73.873785),
    "SJ21": CLLocationCoordinate2D(latitude: 40.68141, longitude: -73.880039),
    "SJ22": CLLocationCoordinate2D(latitude: 40.679947, longitude: -73.884639),
    "SJ23": CLLocationCoordinate2D(latitude: 40.678024, longitude: -73.891688),
    "SJ24": CLLocationCoordinate2D(latitude: 40.676992, longitude: -73.898654),
    "SJ27": CLLocationCoordinate2D(latitude: 40.679498, longitude: -73.904512),
    "SJ28": CLLocationCoordinate2D(latitude: 40.682893, longitude: -73.910456),
    "SJ29": CLLocationCoordinate2D(latitude: 40.68637, longitude: -73.916559),
    "SJ30": CLLocationCoordinate2D(latitude: 40.68963, longitude: -73.92227),
    "SJ31": CLLocationCoordinate2D(latitude: 40.693342, longitude: -73.928814),
    "SL01": CLLocationCoordinate2D(latitude: 40.739777, longitude: -74.002578),
    "SL02": CLLocationCoordinate2D(latitude: 40.737335, longitude: -73.996786),
    "SL03": CLLocationCoordinate2D(latitude: 40.734789, longitude: -73.99073),
    "SL05": CLLocationCoordinate2D(latitude: 40.732849, longitude: -73.986122),
    "SL06": CLLocationCoordinate2D(latitude: 40.730953, longitude: -73.981628),
    "SL08": CLLocationCoordinate2D(latitude: 40.717304, longitude: -73.956872),
    "SL10": CLLocationCoordinate2D(latitude: 40.714063, longitude: -73.950275),
    "SL11": CLLocationCoordinate2D(latitude: 40.714565, longitude: -73.944053),
    "SL12": CLLocationCoordinate2D(latitude: 40.711926, longitude: -73.94067),
    "SL13": CLLocationCoordinate2D(latitude: 40.707739, longitude: -73.93985),
    "SL14": CLLocationCoordinate2D(latitude: 40.706152, longitude: -73.933147),
    "SL15": CLLocationCoordinate2D(latitude: 40.706607, longitude: -73.922913),
    "SL16": CLLocationCoordinate2D(latitude: 40.703811, longitude: -73.918425),
    "SL17": CLLocationCoordinate2D(latitude: 40.699814, longitude: -73.911586),
    "SL19": CLLocationCoordinate2D(latitude: 40.695602, longitude: -73.904084),
    "SL20": CLLocationCoordinate2D(latitude: 40.688764, longitude: -73.904046),
    "SL21": CLLocationCoordinate2D(latitude: 40.682829, longitude: -73.905249),
    "SL22": CLLocationCoordinate2D(latitude: 40.678856, longitude: -73.90324),
    "SL24": CLLocationCoordinate2D(latitude: 40.675345, longitude: -73.903097),
    "SL25": CLLocationCoordinate2D(latitude: 40.669367, longitude: -73.901975),
    "SL26": CLLocationCoordinate2D(latitude: 40.664038, longitude: -73.900571),
    "SL27": CLLocationCoordinate2D(latitude: 40.658733, longitude: -73.899232),
    "SL28": CLLocationCoordinate2D(latitude: 40.650573, longitude: -73.899485),
    "SL29": CLLocationCoordinate2D(latitude: 40.646654, longitude: -73.90185),
    "SM01": CLLocationCoordinate2D(latitude: 40.711396, longitude: -73.889601),
    "SM04": CLLocationCoordinate2D(latitude: 40.706186, longitude: -73.895877),
    "SM05": CLLocationCoordinate2D(latitude: 40.704423, longitude: -73.903077),
    "SM06": CLLocationCoordinate2D(latitude: 40.702762, longitude: -73.90774),
    "SM08": CLLocationCoordinate2D(latitude: 40.69943, longitude: -73.912385),
    "SM09": CLLocationCoordinate2D(latitude: 40.698664, longitude: -73.919711),
    "SM10": CLLocationCoordinate2D(latitude: 40.697857, longitude: -73.927397),
    "SM11": CLLocationCoordinate2D(latitude: 40.697207, longitude: -73.935657),
    "SM12": CLLocationCoordinate2D(latitude: 40.70026, longitude: -73.941126),
    "SM13": CLLocationCoordinate2D(latitude: 40.703869, longitude: -73.947408),
    "SM14": CLLocationCoordinate2D(latitude: 40.70687, longitude: -73.953431),
    "SM16": CLLocationCoordinate2D(latitude: 40.708359, longitude: -73.957757),
    "SM18": CLLocationCoordinate2D(latitude: 40.718315, longitude: -73.987437),
    "SM19": CLLocationCoordinate2D(latitude: 40.72028, longitude: -73.993915),
    "SM20": CLLocationCoordinate2D(latitude: 40.718092, longitude: -73.999892),
    "SM21": CLLocationCoordinate2D(latitude: 40.713243, longitude: -74.003401),
    "SM22": CLLocationCoordinate2D(latitude: 40.710374, longitude: -74.007582),
    "SM23": CLLocationCoordinate2D(latitude: 40.706476, longitude: -74.011056),
    "SN02": CLLocationCoordinate2D(latitude: 40.635064, longitude: -74.011719),
    "SN03": CLLocationCoordinate2D(latitude: 40.631386, longitude: -74.005351),
    "SN04": CLLocationCoordinate2D(latitude: 40.624842, longitude: -73.996353),
    "SN05": CLLocationCoordinate2D(latitude: 40.620671, longitude: -73.990414),
    "SN06": CLLocationCoordinate2D(latitude: 40.61741, longitude: -73.985026),
    "SN07": CLLocationCoordinate2D(latitude: 40.611815, longitude: -73.981848),
    "SN08": CLLocationCoordinate2D(latitude: 40.603923, longitude: -73.980353),
    "SN09": CLLocationCoordinate2D(latitude: 40.597473, longitude: -73.979137),
    "SN10": CLLocationCoordinate2D(latitude: 40.592721, longitude: -73.97823),
    "SQ01": CLLocationCoordinate2D(latitude: 40.718383, longitude: -74.00046),
    "SQ03": CLLocationCoordinate2D(latitude: 40.768799, longitude: -73.958424),
    "SQ04": CLLocationCoordinate2D(latitude: 40.777891, longitude: -73.951787),
    "SQ05": CLLocationCoordinate2D(latitude: 40.784318, longitude: -73.947152),
    "SR01": CLLocationCoordinate2D(latitude: 40.775036, longitude: -73.912034),
    "SR03": CLLocationCoordinate2D(latitude: 40.770258, longitude: -73.917843),
    "SR04": CLLocationCoordinate2D(latitude: 40.766779, longitude: -73.921479),
    "SR05": CLLocationCoordinate2D(latitude: 40.76182, longitude: -73.925508),
    "SR06": CLLocationCoordinate2D(latitude: 40.756804, longitude: -73.929575),
    "SR08": CLLocationCoordinate2D(latitude: 40.752882, longitude: -73.932755),
    "SR09": CLLocationCoordinate2D(latitude: 40.750582, longitude: -73.940202),
    "SR11": CLLocationCoordinate2D(latitude: 40.76266, longitude: -73.967258),
    "SR13": CLLocationCoordinate2D(latitude: 40.764811, longitude: -73.973347),
    "SR14": CLLocationCoordinate2D(latitude: 40.764664, longitude: -73.980658),
    "SR15": CLLocationCoordinate2D(latitude: 40.759901, longitude: -73.984139),
    "SR16": CLLocationCoordinate2D(latitude: 40.754672, longitude: -73.986754),
    "SR17": CLLocationCoordinate2D(latitude: 40.749567, longitude: -73.98795),
    "SR18": CLLocationCoordinate2D(latitude: 40.745494, longitude: -73.988691),
    "SR19": CLLocationCoordinate2D(latitude: 40.741303, longitude: -73.989344),
    "SR20": CLLocationCoordinate2D(latitude: 40.735736, longitude: -73.990568),
    "SR21": CLLocationCoordinate2D(latitude: 40.730328, longitude: -73.992629),
    "SR22": CLLocationCoordinate2D(latitude: 40.724329, longitude: -73.997702),
    "SR23": CLLocationCoordinate2D(latitude: 40.719527, longitude: -74.001775),
    "SR24": CLLocationCoordinate2D(latitude: 40.713282, longitude: -74.006978),
    "SR25": CLLocationCoordinate2D(latitude: 40.710668, longitude: -74.011029),
    "SR26": CLLocationCoordinate2D(latitude: 40.70722, longitude: -74.013342),
    "SR27": CLLocationCoordinate2D(latitude: 40.703087, longitude: -74.012994),
    "SR28": CLLocationCoordinate2D(latitude: 40.6941, longitude: -73.991777),
    "SR29": CLLocationCoordinate2D(latitude: 40.69218, longitude: -73.985942),
    "SR30": CLLocationCoordinate2D(latitude: 40.690635, longitude: -73.981824),
    "SR31": CLLocationCoordinate2D(latitude: 40.683666, longitude: -73.97881),
    "SR32": CLLocationCoordinate2D(latitude: 40.677316, longitude: -73.98311),
    "SR33": CLLocationCoordinate2D(latitude: 40.670847, longitude: -73.988302),
    "SR34": CLLocationCoordinate2D(latitude: 40.665414, longitude: -73.992872),
    "SR35": CLLocationCoordinate2D(latitude: 40.660397, longitude: -73.998091),
    "SR36": CLLocationCoordinate2D(latitude: 40.655144, longitude: -74.003549),
    "SR39": CLLocationCoordinate2D(latitude: 40.648939, longitude: -74.010006),
    "SR40": CLLocationCoordinate2D(latitude: 40.645069, longitude: -74.014034),
    "SR41": CLLocationCoordinate2D(latitude: 40.641362, longitude: -74.017881),
    "SR42": CLLocationCoordinate2D(latitude: 40.634967, longitude: -74.023377),
    "SR43": CLLocationCoordinate2D(latitude: 40.629742, longitude: -74.02551),
    "SR44": CLLocationCoordinate2D(latitude: 40.622687, longitude: -74.028398),
    "SR45": CLLocationCoordinate2D(latitude: 40.616622, longitude: -74.030876),
    "SS01": CLLocationCoordinate2D(latitude: 40.680596, longitude: -73.955827),
    "SS03": CLLocationCoordinate2D(latitude: 40.674772, longitude: -73.957624),
    "SS04": CLLocationCoordinate2D(latitude: 40.670343, longitude: -73.959245),
    "SS09": CLLocationCoordinate2D(latitude: 40.512764, longitude: -74.251961),
    "SS11": CLLocationCoordinate2D(latitude: 40.516578, longitude: -74.242096),
    "SS13": CLLocationCoordinate2D(latitude: 40.519631, longitude: -74.229141),
    "SS14": CLLocationCoordinate2D(latitude: 40.52241, longitude: -74.217847),
    "SS15": CLLocationCoordinate2D(latitude: 40.525507, longitude: -74.200064),
    "SS16": CLLocationCoordinate2D(latitude: 40.533674, longitude: -74.191794),
    "SS17": CLLocationCoordinate2D(latitude: 40.54046, longitude: -74.178217),
    "SS18": CLLocationCoordinate2D(latitude: 40.544601, longitude: -74.16457),
    "SS19": CLLocationCoordinate2D(latitude: 40.551231, longitude: -74.151399),
    "SS20": CLLocationCoordinate2D(latitude: 40.5564, longitude: -74.136907),
    "SS21": CLLocationCoordinate2D(latitude: 40.56511, longitude: -74.12632),
    "SS22": CLLocationCoordinate2D(latitude: 40.57348, longitude: -74.11721),
    "SS23": CLLocationCoordinate2D(latitude: 40.578965, longitude: -74.109704),
    "SS24": CLLocationCoordinate2D(latitude: 40.583591, longitude: -74.103338),
    "SS25": CLLocationCoordinate2D(latitude: 40.588849, longitude: -74.09609),
    "SS26": CLLocationCoordinate2D(latitude: 40.596612, longitude: -74.087368),
    "SS27": CLLocationCoordinate2D(latitude: 40.603117, longitude: -74.084087),
    "SS28": CLLocationCoordinate2D(latitude: 40.621319, longitude: -74.071402),
    "SS29": CLLocationCoordinate2D(latitude: 40.627915, longitude: -74.075162),
    "SS30": CLLocationCoordinate2D(latitude: 40.636949, longitude: -74.074835),
    "SS31": CLLocationCoordinate2D(latitude: 40.643748, longitude: -74.073643),

    // WMATA (DC Metro)
    "A01": CLLocationCoordinate2D(latitude: 38.898303, longitude: -77.028099),
    "A02": CLLocationCoordinate2D(latitude: 38.903192, longitude: -77.039766),
    "A03": CLLocationCoordinate2D(latitude: 38.909499, longitude: -77.04362),
    "A04": CLLocationCoordinate2D(latitude: 38.924999, longitude: -77.052648),
    "A05": CLLocationCoordinate2D(latitude: 38.934703, longitude: -77.058226),
    "A06": CLLocationCoordinate2D(latitude: 38.94362, longitude: -77.063511),
    "A07": CLLocationCoordinate2D(latitude: 38.947808, longitude: -77.079615),
    "A08": CLLocationCoordinate2D(latitude: 38.960744, longitude: -77.085969),
    "A09": CLLocationCoordinate2D(latitude: 38.984282, longitude: -77.094431),
    "A10": CLLocationCoordinate2D(latitude: 38.999947, longitude: -77.097253),
    "A11": CLLocationCoordinate2D(latitude: 39.029158, longitude: -77.10415),
    "A12": CLLocationCoordinate2D(latitude: 39.048043, longitude: -77.113131),
    "A13": CLLocationCoordinate2D(latitude: 39.062359, longitude: -77.121113),
    "A14": CLLocationCoordinate2D(latitude: 39.084215, longitude: -77.146424),
    "A15": CLLocationCoordinate2D(latitude: 39.119819, longitude: -77.164921),
    "B01": CLLocationCoordinate2D(latitude: 38.89834, longitude: -77.021851),
    "B02": CLLocationCoordinate2D(latitude: 38.896084, longitude: -77.016643),
    "B03": CLLocationCoordinate2D(latitude: 38.897723, longitude: -77.006745),
    "B04": CLLocationCoordinate2D(latitude: 38.920741, longitude: -76.995984),
    "B05": CLLocationCoordinate2D(latitude: 38.933234, longitude: -76.994544),
    "B06": CLLocationCoordinate2D(latitude: 38.951777, longitude: -77.002174),
    "B07": CLLocationCoordinate2D(latitude: 38.975532, longitude: -77.017834),
    "B08": CLLocationCoordinate2D(latitude: 38.993841, longitude: -77.031321),
    "B09": CLLocationCoordinate2D(latitude: 39.015413, longitude: -77.042953),
    "B10": CLLocationCoordinate2D(latitude: 39.038558, longitude: -77.051098),
    "B11": CLLocationCoordinate2D(latitude: 39.061713, longitude: -77.05341),
    "B35": CLLocationCoordinate2D(latitude: 38.907407, longitude: -77.002961),
    "C01": CLLocationCoordinate2D(latitude: 38.898303, longitude: -77.028099),
    "C02": CLLocationCoordinate2D(latitude: 38.901316, longitude: -77.033652),
    "C03": CLLocationCoordinate2D(latitude: 38.901311, longitude: -77.03981),
    "C04": CLLocationCoordinate2D(latitude: 38.900599, longitude: -77.050273),
    "C05": CLLocationCoordinate2D(latitude: 38.896595, longitude: -77.07146),
    "C06": CLLocationCoordinate2D(latitude: 38.884574, longitude: -77.063108),
    "C07": CLLocationCoordinate2D(latitude: 38.869349, longitude: -77.054013),
    "C08": CLLocationCoordinate2D(latitude: 38.863045, longitude: -77.059507),
    "C09": CLLocationCoordinate2D(latitude: 38.85779, longitude: -77.050589),
    "C10": CLLocationCoordinate2D(latitude: 38.852985, longitude: -77.043805),
    "C11": CLLocationCoordinate2D(latitude: 38.83321, longitude: -77.04642),
    "C12": CLLocationCoordinate2D(latitude: 38.814009, longitude: -77.053763),
    "C13": CLLocationCoordinate2D(latitude: 38.806474, longitude: -77.061115),
    "C14": CLLocationCoordinate2D(latitude: 38.800313, longitude: -77.071173),
    "C15": CLLocationCoordinate2D(latitude: 38.793841, longitude: -77.075301),
    "D01": CLLocationCoordinate2D(latitude: 38.893757, longitude: -77.028218),
    "D02": CLLocationCoordinate2D(latitude: 38.888022, longitude: -77.028232),
    "D03": CLLocationCoordinate2D(latitude: 38.884775, longitude: -77.021964),
    "D04": CLLocationCoordinate2D(latitude: 38.884958, longitude: -77.01586),
    "D05": CLLocationCoordinate2D(latitude: 38.884968, longitude: -77.005137),
    "D06": CLLocationCoordinate2D(latitude: 38.884124, longitude: -76.995334),
    "D07": CLLocationCoordinate2D(latitude: 38.880841, longitude: -76.985721),
    "D08": CLLocationCoordinate2D(latitude: 38.88594, longitude: -76.977485),
    "D09": CLLocationCoordinate2D(latitude: 38.898284, longitude: -76.948042),
    "D10": CLLocationCoordinate2D(latitude: 38.907734, longitude: -76.936177),
    "D11": CLLocationCoordinate2D(latitude: 38.91652, longitude: -76.915427),
    "D12": CLLocationCoordinate2D(latitude: 38.934411, longitude: -76.890988),
    "D13": CLLocationCoordinate2D(latitude: 38.947674, longitude: -76.872144),
    "E01": CLLocationCoordinate2D(latitude: 38.905604, longitude: -77.022256),
    "E02": CLLocationCoordinate2D(latitude: 38.912919, longitude: -77.022194),
    "E03": CLLocationCoordinate2D(latitude: 38.916489, longitude: -77.028938),
    "E04": CLLocationCoordinate2D(latitude: 38.928672, longitude: -77.032775),
    "E05": CLLocationCoordinate2D(latitude: 38.936077, longitude: -77.024728),
    "E06": CLLocationCoordinate2D(latitude: 38.951777, longitude: -77.002174),
    "E07": CLLocationCoordinate2D(latitude: 38.954931, longitude: -76.969881),
    "E08": CLLocationCoordinate2D(latitude: 38.965276, longitude: -76.956182),
    "E09": CLLocationCoordinate2D(latitude: 38.978523, longitude: -76.928432),
    "E10": CLLocationCoordinate2D(latitude: 39.011036, longitude: -76.911362),
    "F01": CLLocationCoordinate2D(latitude: 38.89834, longitude: -77.021851),
    "F02": CLLocationCoordinate2D(latitude: 38.893893, longitude: -77.021902),
    "F03": CLLocationCoordinate2D(latitude: 38.884775, longitude: -77.021964),
    "F04": CLLocationCoordinate2D(latitude: 38.876221, longitude: -77.017491),
    "F05": CLLocationCoordinate2D(latitude: 38.876588, longitude: -77.005086),
    "F06": CLLocationCoordinate2D(latitude: 38.862072, longitude: -76.995648),
    "F07": CLLocationCoordinate2D(latitude: 38.845334, longitude: -76.98817),
    "F08": CLLocationCoordinate2D(latitude: 38.840974, longitude: -76.97536),
    "F09": CLLocationCoordinate2D(latitude: 38.851187, longitude: -76.956565),
    "F10": CLLocationCoordinate2D(latitude: 38.843891, longitude: -76.932022),
    "F11": CLLocationCoordinate2D(latitude: 38.826995, longitude: -76.912134),
    "G01": CLLocationCoordinate2D(latitude: 38.890488, longitude: -76.938291),
    "G02": CLLocationCoordinate2D(latitude: 38.889757, longitude: -76.913382),
    "G03": CLLocationCoordinate2D(latitude: 38.886713, longitude: -76.893592),
    "G04": CLLocationCoordinate2D(latitude: 38.8913, longitude: -76.8682),
    "G05": CLLocationCoordinate2D(latitude: 38.9008, longitude: -76.8449),
    "J02": CLLocationCoordinate2D(latitude: 38.799193, longitude: -77.129407),
    "J03": CLLocationCoordinate2D(latitude: 38.766129, longitude: -77.168797),
    "K01": CLLocationCoordinate2D(latitude: 38.891499, longitude: -77.08391),
    "K02": CLLocationCoordinate2D(latitude: 38.886373, longitude: -77.096963),
    "K03": CLLocationCoordinate2D(latitude: 38.88331, longitude: -77.104267),
    "K04": CLLocationCoordinate2D(latitude: 38.882071, longitude: -77.111845),
    "K05": CLLocationCoordinate2D(latitude: 38.885841, longitude: -77.157177),
    "K06": CLLocationCoordinate2D(latitude: 38.90067, longitude: -77.189394),
    "K07": CLLocationCoordinate2D(latitude: 38.883015, longitude: -77.228939),
    "K08": CLLocationCoordinate2D(latitude: 38.877693, longitude: -77.271562),
    "N01": CLLocationCoordinate2D(latitude: 38.924478, longitude: -77.210167),
    "N02": CLLocationCoordinate2D(latitude: 38.920056, longitude: -77.223314),
    "N03": CLLocationCoordinate2D(latitude: 38.919749, longitude: -77.235192),
    "N04": CLLocationCoordinate2D(latitude: 38.929273, longitude: -77.241988),
    "N06": CLLocationCoordinate2D(latitude: 38.947753, longitude: -77.340179),
    "N07": CLLocationCoordinate2D(latitude: 38.952768, longitude: -77.360185),
    "N08": CLLocationCoordinate2D(latitude: 38.952821, longitude: -77.385178),
    "N09": CLLocationCoordinate2D(latitude: 38.960758, longitude: -77.415295),
    "N10": CLLocationCoordinate2D(latitude: 38.955784, longitude: -77.448148),
    "N11": CLLocationCoordinate2D(latitude: 38.99204, longitude: -77.460685),
    "N12": CLLocationCoordinate2D(latitude: 39.005283, longitude: -77.491537),

    // MBTA Commuter Rail stations (shared Amtrak stations BOS, BBY, PVD, RTE, WOR already above)
    "BNST": CLLocationCoordinate2D(latitude: 42.365577, longitude: -71.06129),
    "BPOR": CLLocationCoordinate2D(latitude: 42.3884, longitude: -71.119149),
    "BRUG": CLLocationCoordinate2D(latitude: 42.336377, longitude: -71.088961),
    "BFHL": CLLocationCoordinate2D(latitude: 42.300713, longitude: -71.113943),
    "BHPK": CLLocationCoordinate2D(latitude: 42.25503, longitude: -71.125526),
    "BRDV": CLLocationCoordinate2D(latitude: 42.238405, longitude: -71.133246),
    "BCJN": CLLocationCoordinate2D(latitude: 42.163204, longitude: -71.15376),
    "BJFK": CLLocationCoordinate2D(latitude: 42.320685, longitude: -71.052391),
    "BQNC": CLLocationCoordinate2D(latitude: 42.251809, longitude: -71.005409),
    "BBRN": CLLocationCoordinate2D(latitude: 42.2078543, longitude: -71.0011385),
    "BCHE": CLLocationCoordinate2D(latitude: 42.397024, longitude: -71.041314),
    "BMAL": CLLocationCoordinate2D(latitude: 42.426632, longitude: -71.07411),
    "BOKG": CLLocationCoordinate2D(latitude: 42.43668, longitude: -71.071097),
    // Fairmount Line
    "BNMK": CLLocationCoordinate2D(latitude: 42.327415, longitude: -71.065674),
    "BUPH": CLLocationCoordinate2D(latitude: 42.319125, longitude: -71.068627),
    "BFCG": CLLocationCoordinate2D(latitude: 42.305037, longitude: -71.076833),
    "BTLB": CLLocationCoordinate2D(latitude: 42.292246, longitude: -71.07814),
    "BMRT": CLLocationCoordinate2D(latitude: 42.280994, longitude: -71.085475),
    "BBHA": CLLocationCoordinate2D(latitude: 42.271466, longitude: -71.095782),
    "BFMT": CLLocationCoordinate2D(latitude: 42.253638, longitude: -71.11927),
    // Franklin/Foxboro Line
    "BEND": CLLocationCoordinate2D(latitude: 42.233249, longitude: -71.158647),
    "BDCC": CLLocationCoordinate2D(latitude: 42.227079, longitude: -71.174254),
    "BISL": CLLocationCoordinate2D(latitude: 42.22105, longitude: -71.183961),
    "BNWD": CLLocationCoordinate2D(latitude: 42.196857, longitude: -71.196688),
    "BNWC": CLLocationCoordinate2D(latitude: 42.188775, longitude: -71.199665),
    "BWDG": CLLocationCoordinate2D(latitude: 42.172127, longitude: -71.219366),
    "BPLM": CLLocationCoordinate2D(latitude: 42.159123, longitude: -71.236125),
    "BWAL": CLLocationCoordinate2D(latitude: 42.145477, longitude: -71.25779),
    "BNFK": CLLocationCoordinate2D(latitude: 42.120694, longitude: -71.325217),
    "BFRK": CLLocationCoordinate2D(latitude: 42.083238, longitude: -71.396102),
    "BFPK": CLLocationCoordinate2D(latitude: 42.089941, longitude: -71.43902),
    "BFOX": CLLocationCoordinate2D(latitude: 42.0951, longitude: -71.26151),
    // Providence/Stoughton Line
    "BSHA": CLLocationCoordinate2D(latitude: 42.124553, longitude: -71.184468),
    "BMAN": CLLocationCoordinate2D(latitude: 42.032787, longitude: -71.219917),
    "BATT": CLLocationCoordinate2D(latitude: 41.940739, longitude: -71.285094),
    "BSAT": CLLocationCoordinate2D(latitude: 41.897943, longitude: -71.354621),
    "BPCF": CLLocationCoordinate2D(latitude: 41.878762, longitude: -71.392),
    "BTFG": CLLocationCoordinate2D(latitude: 41.726599, longitude: -71.442453),
    "BWKF": CLLocationCoordinate2D(latitude: 41.581289, longitude: -71.491147),
    "BCNC": CLLocationCoordinate2D(latitude: 42.157095, longitude: -71.14628),
    "BSTO": CLLocationCoordinate2D(latitude: 42.124084, longitude: -71.103627),
    // Needham Line
    "BRSV": CLLocationCoordinate2D(latitude: 42.287442, longitude: -71.130283),
    "BBLV": CLLocationCoordinate2D(latitude: 42.286588, longitude: -71.145557),
    "BHLD": CLLocationCoordinate2D(latitude: 42.284969, longitude: -71.153937),
    "BWRX": CLLocationCoordinate2D(latitude: 42.281358, longitude: -71.160065),
    "BHRS": CLLocationCoordinate2D(latitude: 42.275648, longitude: -71.215528),
    "BNJN": CLLocationCoordinate2D(latitude: 42.273187, longitude: -71.235559),
    "BNDC": CLLocationCoordinate2D(latitude: 42.280775, longitude: -71.237686),
    "BNDH": CLLocationCoordinate2D(latitude: 42.293444, longitude: -71.236027),
    // Worcester/Framingham Line
    "BLDN": CLLocationCoordinate2D(latitude: 42.347581, longitude: -71.099974),
    "BBLN": CLLocationCoordinate2D(latitude: 42.357293, longitude: -71.139883),
    "BNVL": CLLocationCoordinate2D(latitude: 42.351702, longitude: -71.205408),
    "BWNT": CLLocationCoordinate2D(latitude: 42.347878, longitude: -71.230528),
    "BAUB": CLLocationCoordinate2D(latitude: 42.345833, longitude: -71.250373),
    "BWFM": CLLocationCoordinate2D(latitude: 42.323608, longitude: -71.272288),
    "BWHL": CLLocationCoordinate2D(latitude: 42.31037, longitude: -71.277044),
    "BWSQ": CLLocationCoordinate2D(latitude: 42.297526, longitude: -71.294173),
    "BNTC": CLLocationCoordinate2D(latitude: 42.285719, longitude: -71.347133),
    "BWNA": CLLocationCoordinate2D(latitude: 42.283064, longitude: -71.391797),
    "BFRM": CLLocationCoordinate2D(latitude: 42.276108, longitude: -71.420055),
    "BASH": CLLocationCoordinate2D(latitude: 42.26149, longitude: -71.482161),
    "BSBO": CLLocationCoordinate2D(latitude: 42.267024, longitude: -71.524371),
    "BWSB": CLLocationCoordinate2D(latitude: 42.269644, longitude: -71.647076),
    "BGRF": CLLocationCoordinate2D(latitude: 42.2466, longitude: -71.685325),
    // Greenbush Line
    "BWLE": CLLocationCoordinate2D(latitude: 42.221503, longitude: -70.968152),
    "BEWY": CLLocationCoordinate2D(latitude: 42.2191, longitude: -70.9214),
    "BWHI": CLLocationCoordinate2D(latitude: 42.235838, longitude: -70.902708),
    "BNAN": CLLocationCoordinate2D(latitude: 42.244959, longitude: -70.869205),
    "BCOH": CLLocationCoordinate2D(latitude: 42.24421, longitude: -70.837529),
    "BNSC": CLLocationCoordinate2D(latitude: 42.219528, longitude: -70.788602),
    "BGRB": CLLocationCoordinate2D(latitude: 42.178776, longitude: -70.746641),
    // Kingston Line
    "BSWY": CLLocationCoordinate2D(latitude: 42.155025, longitude: -70.953302),
    "BABI": CLLocationCoordinate2D(latitude: 42.107156, longitude: -70.934405),
    "BWHT": CLLocationCoordinate2D(latitude: 42.082749, longitude: -70.923411),
    "BHAN": CLLocationCoordinate2D(latitude: 42.043967, longitude: -70.882438),
    "BHLX": CLLocationCoordinate2D(latitude: 42.014739, longitude: -70.824263),
    "BKNG": CLLocationCoordinate2D(latitude: 41.97762, longitude: -70.721709),
    "BPLY": CLLocationCoordinate2D(latitude: 41.981278, longitude: -70.690421),
    // Middleborough/New Bedford Line
    "BHLR": CLLocationCoordinate2D(latitude: 42.156343, longitude: -71.027371),
    "BMTL": CLLocationCoordinate2D(latitude: 42.106555, longitude: -71.022001),
    "BBRO": CLLocationCoordinate2D(latitude: 42.084659, longitude: -71.016534),
    "BCMP": CLLocationCoordinate2D(latitude: 42.060951, longitude: -71.011004),
    "BBDG": CLLocationCoordinate2D(latitude: 41.984916, longitude: -70.96537),
    "BLKV": CLLocationCoordinate2D(latitude: 41.87821, longitude: -70.918444),
    "BMID": CLLocationCoordinate2D(latitude: 41.887, longitude: -70.923209),
    "BETN": CLLocationCoordinate2D(latitude: 41.868197, longitude: -71.061694),
    "BFTW": CLLocationCoordinate2D(latitude: 41.773672, longitude: -71.090733),
    "BFRD": CLLocationCoordinate2D(latitude: 41.713982, longitude: -71.154182),
    "BCST": CLLocationCoordinate2D(latitude: 41.674308, longitude: -70.939322),
    "BNBD": CLLocationCoordinate2D(latitude: 41.643703, longitude: -70.9252),
    // Newburyport/Rockport Line
    "BRWK": CLLocationCoordinate2D(latitude: 42.449927, longitude: -70.969848),
    "BLNN": CLLocationCoordinate2D(latitude: 42.462953, longitude: -70.945421),
    "BLNI": CLLocationCoordinate2D(latitude: 42.4652901, longitude: -70.9404344),
    "BSWP": CLLocationCoordinate2D(latitude: 42.473743, longitude: -70.922537),
    "BSLM": CLLocationCoordinate2D(latitude: 42.524792, longitude: -70.895876),
    "BBEV": CLLocationCoordinate2D(latitude: 42.547276, longitude: -70.885432),
    "BNBV": CLLocationCoordinate2D(latitude: 42.583779, longitude: -70.883851),
    "BHWN": CLLocationCoordinate2D(latitude: 42.609212, longitude: -70.874801),
    "BIPS": CLLocationCoordinate2D(latitude: 42.676921, longitude: -70.840589),
    "BROW": CLLocationCoordinate2D(latitude: 42.726845, longitude: -70.859034),
    "BNBP": CLLocationCoordinate2D(latitude: 42.797837, longitude: -70.87797),
    "BMTS": CLLocationCoordinate2D(latitude: 42.562171, longitude: -70.869254),
    "BPRC": CLLocationCoordinate2D(latitude: 42.559446, longitude: -70.825541),
    "BBFM": CLLocationCoordinate2D(latitude: 42.561651, longitude: -70.811405),
    "BMCH": CLLocationCoordinate2D(latitude: 42.573687, longitude: -70.77009),
    "BWGL": CLLocationCoordinate2D(latitude: 42.611933, longitude: -70.705417),
    "BGLO": CLLocationCoordinate2D(latitude: 42.616799, longitude: -70.668345),
    "BRPT": CLLocationCoordinate2D(latitude: 42.655491, longitude: -70.627055),
    // Haverhill Line
    "BWYH": CLLocationCoordinate2D(latitude: 42.451731, longitude: -71.069379),
    "BMCP": CLLocationCoordinate2D(latitude: 42.458768, longitude: -71.069789),
    "BMHG": CLLocationCoordinate2D(latitude: 42.469464, longitude: -71.068297),
    "BGNW": CLLocationCoordinate2D(latitude: 42.483005, longitude: -71.067247),
    "BWAK": CLLocationCoordinate2D(latitude: 42.502126, longitude: -71.075566),
    "BRDG": CLLocationCoordinate2D(latitude: 42.52221, longitude: -71.108294),
    "BNWI": CLLocationCoordinate2D(latitude: 42.571073, longitude: -71.160939),
    "BBVL": CLLocationCoordinate2D(latitude: 42.627356, longitude: -71.159962),
    "BAND": CLLocationCoordinate2D(latitude: 42.658336, longitude: -71.144502),
    "BLAW": CLLocationCoordinate2D(latitude: 42.701806, longitude: -71.15198),
    "BBRD": CLLocationCoordinate2D(latitude: 42.766912, longitude: -71.088411),
    "BHAV": CLLocationCoordinate2D(latitude: 42.773474, longitude: -71.086237),
    // Lowell Line
    "BWMF": CLLocationCoordinate2D(latitude: 42.421776, longitude: -71.133342),
    "BWDM": CLLocationCoordinate2D(latitude: 42.444948, longitude: -71.140169),
    "BWNC": CLLocationCoordinate2D(latitude: 42.451088, longitude: -71.13783),
    "BMSH": CLLocationCoordinate2D(latitude: 42.504402, longitude: -71.137618),
    "BAWB": CLLocationCoordinate2D(latitude: 42.516987, longitude: -71.144475),
    "BWLM": CLLocationCoordinate2D(latitude: 42.546624, longitude: -71.174334),
    "BNBL": CLLocationCoordinate2D(latitude: 42.593248, longitude: -71.280995),
    "BLOW": CLLocationCoordinate2D(latitude: 42.63535, longitude: -71.314543),
    // Fitchburg Line
    "BBMT": CLLocationCoordinate2D(latitude: 42.395896, longitude: -71.17619),
    "BWAV": CLLocationCoordinate2D(latitude: 42.3876, longitude: -71.190744),
    "BWTH": CLLocationCoordinate2D(latitude: 42.374296, longitude: -71.235615),
    "BBNR": CLLocationCoordinate2D(latitude: 42.361898, longitude: -71.260065),
    "BKGN": CLLocationCoordinate2D(latitude: 42.37897, longitude: -71.282411),
    "BHST": CLLocationCoordinate2D(latitude: 42.385755, longitude: -71.289203),
    "BSLH": CLLocationCoordinate2D(latitude: 42.395625, longitude: -71.302357),
    "BLIN": CLLocationCoordinate2D(latitude: 42.413641, longitude: -71.325512),
    "BCON": CLLocationCoordinate2D(latitude: 42.456565, longitude: -71.357677),
    "BWCN": CLLocationCoordinate2D(latitude: 42.457043, longitude: -71.392892),
    "BSAC": CLLocationCoordinate2D(latitude: 42.460375, longitude: -71.457744),
    "BLIT": CLLocationCoordinate2D(latitude: 42.519236, longitude: -71.502643),
    "BAYE": CLLocationCoordinate2D(latitude: 42.559074, longitude: -71.588476),
    "BSHR": CLLocationCoordinate2D(latitude: 42.545089, longitude: -71.648004),
    "BNLM": CLLocationCoordinate2D(latitude: 42.539017, longitude: -71.739186),
    "BFIT": CLLocationCoordinate2D(latitude: 42.58072, longitude: -71.792611),
    "BWAC": CLLocationCoordinate2D(latitude: 42.553477, longitude: -71.848488),
    // CapeFlyer
    "BWRV": CLLocationCoordinate2D(latitude: 41.7604, longitude: -70.7171),
    "BBZB": CLLocationCoordinate2D(latitude: 41.744805, longitude: -70.616226),
    "BBNE": CLLocationCoordinate2D(latitude: 41.7464973, longitude: -70.5887722),
    "BHYN": CLLocationCoordinate2D(latitude: 41.660225, longitude: -70.276583),

    // BART
    "BART_12TH": CLLocationCoordinate2D(latitude: 37.803482, longitude: -122.271630),
    "BART_16TH": CLLocationCoordinate2D(latitude: 37.765173, longitude: -122.419704),
    "BART_19TH": CLLocationCoordinate2D(latitude: 37.808078, longitude: -122.268758),
    "BART_24TH": CLLocationCoordinate2D(latitude: 37.752419, longitude: -122.418468),
    "BART_ANTC": CLLocationCoordinate2D(latitude: 37.995373, longitude: -121.780346),
    "BART_ASHB": CLLocationCoordinate2D(latitude: 37.853072, longitude: -122.269771),
    "BART_BALB": CLLocationCoordinate2D(latitude: 37.721747, longitude: -122.447457),
    "BART_BAYF": CLLocationCoordinate2D(latitude: 37.696908, longitude: -122.126446),
    "BART_BERY": CLLocationCoordinate2D(latitude: 37.368473, longitude: -121.874681),
    "BART_CAST": CLLocationCoordinate2D(latitude: 37.690737, longitude: -122.075601),
    "BART_CIVC": CLLocationCoordinate2D(latitude: 37.779408, longitude: -122.413826),
    "BART_COLS": CLLocationCoordinate2D(latitude: 37.753576, longitude: -122.196716),
    "BART_COLM": CLLocationCoordinate2D(latitude: 37.684635, longitude: -122.466157),
    "BART_CONC": CLLocationCoordinate2D(latitude: 37.973757, longitude: -122.029072),
    "BART_DALY": CLLocationCoordinate2D(latitude: 37.706259, longitude: -122.468908),
    "BART_DBRK": CLLocationCoordinate2D(latitude: 37.870110, longitude: -122.268109),
    "BART_DELN": CLLocationCoordinate2D(latitude: 37.925184, longitude: -122.316892),
    "BART_DUBL": CLLocationCoordinate2D(latitude: 37.701646, longitude: -121.899229),
    "BART_EMBR": CLLocationCoordinate2D(latitude: 37.792762, longitude: -122.397037),
    "BART_FRMT": CLLocationCoordinate2D(latitude: 37.557480, longitude: -121.976619),
    "BART_FTVL": CLLocationCoordinate2D(latitude: 37.774841, longitude: -122.224081),
    "BART_GLEN": CLLocationCoordinate2D(latitude: 37.733235, longitude: -122.433515),
    "BART_HAYW": CLLocationCoordinate2D(latitude: 37.669699, longitude: -122.086958),
    "BART_LAFY": CLLocationCoordinate2D(latitude: 37.893183, longitude: -122.124620),
    "BART_LAKE": CLLocationCoordinate2D(latitude: 37.797322, longitude: -122.265247),
    "BART_MCAR": CLLocationCoordinate2D(latitude: 37.828803, longitude: -122.267105),
    "BART_MLBR": CLLocationCoordinate2D(latitude: 37.600237, longitude: -122.386757),
    "BART_MLPT": CLLocationCoordinate2D(latitude: 37.410277, longitude: -121.891081),
    "BART_MONT": CLLocationCoordinate2D(latitude: 37.789173, longitude: -122.401587),
    "BART_NBRK": CLLocationCoordinate2D(latitude: 37.874005, longitude: -122.283523),
    "BART_NCON": CLLocationCoordinate2D(latitude: 38.003383, longitude: -122.024512),
    "BART_OAKL": CLLocationCoordinate2D(latitude: 37.713256, longitude: -122.212237),
    "BART_ORIN": CLLocationCoordinate2D(latitude: 37.878481, longitude: -122.183667),
    "BART_PCTR": CLLocationCoordinate2D(latitude: 38.016847, longitude: -121.889062),
    "BART_PHIL": CLLocationCoordinate2D(latitude: 37.928434, longitude: -122.055971),
    "BART_PITT": CLLocationCoordinate2D(latitude: 38.018910, longitude: -121.944236),
    "BART_PLZA": CLLocationCoordinate2D(latitude: 37.902610, longitude: -122.298920),
    "BART_POWL": CLLocationCoordinate2D(latitude: 37.784606, longitude: -122.407331),
    "BART_RICH": CLLocationCoordinate2D(latitude: 37.936758, longitude: -122.353047),
    "BART_ROCK": CLLocationCoordinate2D(latitude: 37.844755, longitude: -122.251235),
    "BART_SANL": CLLocationCoordinate2D(latitude: 37.721784, longitude: -122.160740),
    "BART_SBRN": CLLocationCoordinate2D(latitude: 37.637730, longitude: -122.416326),
    "BART_SFIA": CLLocationCoordinate2D(latitude: 37.616091, longitude: -122.391954),
    "BART_SHAY": CLLocationCoordinate2D(latitude: 37.634340, longitude: -122.057182),
    "BART_SSAN": CLLocationCoordinate2D(latitude: 37.664462, longitude: -122.444211),
    "BART_UCTY": CLLocationCoordinate2D(latitude: 37.590735, longitude: -122.017248),
    "BART_WARM": CLLocationCoordinate2D(latitude: 37.502285, longitude: -121.939395),
    "BART_WCRK": CLLocationCoordinate2D(latitude: 37.905791, longitude: -122.067327),
    "BART_WDUB": CLLocationCoordinate2D(latitude: 37.699721, longitude: -121.928277),
    "BART_WOAK": CLLocationCoordinate2D(latitude: 37.804888, longitude: -122.295151),

    // SEPTA Regional Rail Stations
    "SEPR90314": CLLocationCoordinate2D(latitude: 39.94361, longitude: -75.21667),
    "SEPR90539": CLLocationCoordinate2D(latitude: 40.25, longitude: -75.27917),
    "SEPR90404": CLLocationCoordinate2D(latitude: 39.87611, longitude: -75.24528),
    "SEPR90403": CLLocationCoordinate2D(latitude: 39.87722, longitude: -75.24139),
    "SEPR90402": CLLocationCoordinate2D(latitude: 39.87806, longitude: -75.24),
    "SEPR90401": CLLocationCoordinate2D(latitude: 39.87944, longitude: -75.23972),
    "SEPR90218": CLLocationCoordinate2D(latitude: 40.00361, longitude: -75.16472),
    "SEPR90526": CLLocationCoordinate2D(latitude: 40.15361, longitude: -75.22472),
    "SEPR90313": CLLocationCoordinate2D(latitude: 39.94472, longitude: -75.23861),
    "SEPR90518": CLLocationCoordinate2D(latitude: 40.00828, longitude: -75.2904),
    "SEPR90412": CLLocationCoordinate2D(latitude: 40.11417, longitude: -75.15305),
    "SEPR90002": CLLocationCoordinate2D(latitude: 40.00111, longitude: -75.22778),
    "SEPR90508": CLLocationCoordinate2D(latitude: 40.04805, longitude: -75.44222),
    "SEPR90318": CLLocationCoordinate2D(latitude: 40.11666, longitude: -75.06834),
    "SEPR90710": CLLocationCoordinate2D(latitude: 40.01056, longitude: -75.06973),
    "SEPR90703": CLLocationCoordinate2D(latitude: 40.10472, longitude: -74.85472),
    "SEPR90516": CLLocationCoordinate2D(latitude: 40.02195, longitude: -75.31639),
    "SEPR90805": CLLocationCoordinate2D(latitude: 40.05111, longitude: -75.19139),
    "SEPR90535": CLLocationCoordinate2D(latitude: 40.28778, longitude: -75.20972),
    "SEPR90808": CLLocationCoordinate2D(latitude: 40.03, longitude: -75.18083),
    "SEPR90813": CLLocationCoordinate2D(latitude: 40.05806, longitude: -75.09278),
    "SEPR90207": CLLocationCoordinate2D(latitude: 39.84972, longitude: -75.36),
    "SEPR90720": CLLocationCoordinate2D(latitude: 40.08111, longitude: -75.20722),
    "SEPR90801": CLLocationCoordinate2D(latitude: 40.07639, longitude: -75.20834),
    "SEPR90202": CLLocationCoordinate2D(latitude: 39.695, longitude: -75.6725),
    "SEPR90204": CLLocationCoordinate2D(latitude: 39.79778, longitude: -75.45222),
    "SEPR90309": CLLocationCoordinate2D(latitude: 39.92667, longitude: -75.29028),
    "SEPR90533": CLLocationCoordinate2D(latitude: 40.26833, longitude: -75.25445),
    "SEPR90225": CLLocationCoordinate2D(latitude: 40.07328, longitude: -75.310944),
    "SEPR90706": CLLocationCoordinate2D(latitude: 40.0709, longitude: -74.95432),
    "SEPR90414": CLLocationCoordinate2D(latitude: 40.13334, longitude: -75.11861),
    "SEPR90704": CLLocationCoordinate2D(latitude: 40.09361, longitude: -74.90667),
    "SEPR90209": CLLocationCoordinate2D(latitude: 39.87194, longitude: -75.33111),
    "SEPR90216": CLLocationCoordinate2D(latitude: 39.90805, longitude: -75.265),
    "SEPR90001": CLLocationCoordinate2D(latitude: 40.00667, longitude: -75.23167),
    "SEPR90217": CLLocationCoordinate2D(latitude: 39.91306, longitude: -75.25445),
    "SEPR90507": CLLocationCoordinate2D(latitude: 40.04306, longitude: -75.46056),
    "SEPR90537": CLLocationCoordinate2D(latitude: 40.29722, longitude: -75.16167),
    "SEPR90509": CLLocationCoordinate2D(latitude: 40.04722, longitude: -75.42278),
    "SEPR90502": CLLocationCoordinate2D(latitude: 40.00219, longitude: -75.71078),
    "SEPR90538": CLLocationCoordinate2D(latitude: 40.30639, longitude: -75.13028),
    "SEPR90219": CLLocationCoordinate2D(latitude: 40.01139, longitude: -75.19195),
    "SEPR90405": CLLocationCoordinate2D(latitude: 39.89278, longitude: -75.24389),
    "SEPR90705": CLLocationCoordinate2D(latitude: 40.08306, longitude: -74.93361),
    "SEPR90208": CLLocationCoordinate2D(latitude: 39.85722, longitude: -75.34222),
    "SEPR90409": CLLocationCoordinate2D(latitude: 40.07139, longitude: -75.12778),
    "SEPR90301": CLLocationCoordinate2D(latitude: 39.9075, longitude: -75.41167),
    "SEPR90504": CLLocationCoordinate2D(latitude: 40.01929, longitude: -75.62171),
    "SEPR90407": CLLocationCoordinate2D(latitude: 40.04055, longitude: -75.13472),
    "SEPR90312": CLLocationCoordinate2D(latitude: 39.93972, longitude: -75.25584),
    "SEPR90214": CLLocationCoordinate2D(latitude: 39.90055, longitude: -75.27972),
    "SEPR90320": CLLocationCoordinate2D(latitude: 40.12778, longitude: -75.02055),
    "SEPR90525": CLLocationCoordinate2D(latitude: 40.13583, longitude: -75.21222),
    "SEPR90532": CLLocationCoordinate2D(latitude: 40.25945, longitude: -75.26611),
    "SEPR90815": CLLocationCoordinate2D(latitude: 40.07639, longitude: -75.08334),
    "SEPR90713": CLLocationCoordinate2D(latitude: 40.0375, longitude: -75.17167),
    "SEPR90310": CLLocationCoordinate2D(latitude: 39.93278, longitude: -75.28222),
    "SEPR90213": CLLocationCoordinate2D(latitude: 39.89639, longitude: -75.29),
    "SEPR90411": CLLocationCoordinate2D(latitude: 40.10139, longitude: -75.15361),
    "SEPR90719": CLLocationCoordinate2D(latitude: 40.0775, longitude: -75.20167),
    "SEPR90004": CLLocationCoordinate2D(latitude: 39.95667, longitude: -75.18166),
    "SEPR90528": CLLocationCoordinate2D(latitude: 40.18472, longitude: -75.25694),
    "SEPR90416": CLLocationCoordinate2D(latitude: 40.17611, longitude: -75.1025),
    "SEPR90517": CLLocationCoordinate2D(latitude: 40.01389, longitude: -75.29972),
    "SEPR90802": CLLocationCoordinate2D(latitude: 40.07056, longitude: -75.21111),
    "SEPR90206": CLLocationCoordinate2D(latitude: 39.83361, longitude: -75.39333),
    "SEPR90708": CLLocationCoordinate2D(latitude: 40.03278, longitude: -75.02361),
    "SEPR90222": CLLocationCoordinate2D(latitude: 40.03417, longitude: -75.23556),
    "SEPR90006": CLLocationCoordinate2D(latitude: 39.9525, longitude: -75.15806),
    "SEPR90410": CLLocationCoordinate2D(latitude: 40.09278, longitude: -75.1375),
    "SEPR90324": CLLocationCoordinate2D(latitude: 40.16083, longitude: -74.9125),
    "SEPR90531": CLLocationCoordinate2D(latitude: 40.24278, longitude: -75.285),
    "SEPR90311": CLLocationCoordinate2D(latitude: 39.9375, longitude: -75.27084),
    "SEPR90812": CLLocationCoordinate2D(latitude: 40.05139, longitude: -75.10306),
    "SEPR90702": CLLocationCoordinate2D(latitude: 40.14028, longitude: -74.81695),
    "SEPR90534": CLLocationCoordinate2D(latitude: 40.27389, longitude: -75.24667),
    "SEPR90227": CLLocationCoordinate2D(latitude: 40.11722, longitude: -75.34861),
    "SEPR90505": CLLocationCoordinate2D(latitude: 40.03639, longitude: -75.51556),
    "SEPR90221": CLLocationCoordinate2D(latitude: 40.02694, longitude: -75.225),
    "SEPR90205": CLLocationCoordinate2D(latitude: 39.82167, longitude: -75.41944),
    "SEPR90317": CLLocationCoordinate2D(latitude: 40.11139, longitude: -75.0925),
    "SEPR90302": CLLocationCoordinate2D(latitude: 39.91444, longitude: -75.395),
    "SEPR90408": CLLocationCoordinate2D(latitude: 40.05944, longitude: -75.12917),
    "SEPR90521": CLLocationCoordinate2D(latitude: 39.99861, longitude: -75.25139),
    "SEPR90223": CLLocationCoordinate2D(latitude: 40.05861, longitude: -75.26639),
    "SEPR90306": CLLocationCoordinate2D(latitude: 39.90778, longitude: -75.32889),
    "SEPR90717": CLLocationCoordinate2D(latitude: 40.06528, longitude: -75.19083),
    "SEPR90303": CLLocationCoordinate2D(latitude: 39.90611, longitude: -75.38861),
    "SEPR90520": CLLocationCoordinate2D(latitude: 40.00472, longitude: -75.26139),
    "SEPR90323": CLLocationCoordinate2D(latitude: 40.14695, longitude: -74.96167),
    "SEPR90536": CLLocationCoordinate2D(latitude: 40.2975, longitude: -75.17973),
    "SEPR90201": CLLocationCoordinate2D(latitude: 39.66969, longitude: -75.75351),
    "SEPR90315": CLLocationCoordinate2D(latitude: 40.10444, longitude: -75.12417),
    "SEPR90228": CLLocationCoordinate2D(latitude: 40.12083, longitude: -75.345),
    "SEPR90226": CLLocationCoordinate2D(latitude: 40.11278, longitude: -75.34417),
    "SEPR90008": CLLocationCoordinate2D(latitude: 39.99222, longitude: -75.15389),
    "SEPR90523": CLLocationCoordinate2D(latitude: 40.11195, longitude: -75.16944),
    "SEPR90711": CLLocationCoordinate2D(latitude: 39.99678, longitude: -75.15511),
    "SEPR90810": CLLocationCoordinate2D(latitude: 39.99778, longitude: -75.15639),
    "SEPR90529": CLLocationCoordinate2D(latitude: 40.21417, longitude: -75.27722),
    "SEPR90212": CLLocationCoordinate2D(latitude: 39.89167, longitude: -75.30167),
    "SEPR90811": CLLocationCoordinate2D(latitude: 40.03333, longitude: -75.12278),
    "SEPR90524": CLLocationCoordinate2D(latitude: 40.11833, longitude: -75.18389),
    "SEPR90522": CLLocationCoordinate2D(latitude: 39.98944, longitude: -75.24944),
    "SEPR90506": CLLocationCoordinate2D(latitude: 40.04276, longitude: -75.48376),
    "SEPR90527": CLLocationCoordinate2D(latitude: 40.17, longitude: -75.24416),
    "SEPR90406": CLLocationCoordinate2D(latitude: 39.94806, longitude: -75.19028),
    "SEPR90530": CLLocationCoordinate2D(latitude: 40.23028, longitude: -75.28167),
    "SEPR90319": CLLocationCoordinate2D(latitude: 40.12194, longitude: -75.04361),
    "SEPR90308": CLLocationCoordinate2D(latitude: 39.92167, longitude: -75.29833),
    "SEPR90211": CLLocationCoordinate2D(latitude: 39.88833, longitude: -75.30889),
    "SEPR90809": CLLocationCoordinate2D(latitude: 40.02333, longitude: -75.17805),
    "SEPR90513": CLLocationCoordinate2D(latitude: 40.04472, longitude: -75.35889),
    "SEPR90804": CLLocationCoordinate2D(latitude: 40.0575, longitude: -75.19473),
    "SEPR90210": CLLocationCoordinate2D(latitude: 39.88055, longitude: -75.32222),
    "SEPR90515": CLLocationCoordinate2D(latitude: 40.02778, longitude: -75.32667),
    "SEPR90413": CLLocationCoordinate2D(latitude: 40.12083, longitude: -75.13416),
    "SEPR90316": CLLocationCoordinate2D(latitude: 40.1075, longitude: -75.11056),
    "SEPR90814": CLLocationCoordinate2D(latitude: 40.06417, longitude: -75.08639),
    "SEPR90307": CLLocationCoordinate2D(latitude: 39.91583, longitude: -75.30972),
    "SEPR90716": CLLocationCoordinate2D(latitude: 40.06278, longitude: -75.18528),
    "SEPR90215": CLLocationCoordinate2D(latitude: 39.90445, longitude: -75.27084),
    "SEPR90321": CLLocationCoordinate2D(latitude: 40.13055, longitude: -75.01195),
    "SEPR90224": CLLocationCoordinate2D(latitude: 40.07417, longitude: -75.28611),
    "SEPR90512": CLLocationCoordinate2D(latitude: 40.04389, longitude: -75.3725),
    "SEPR90803": CLLocationCoordinate2D(latitude: 40.06583, longitude: -75.20444),
    "SEPR90715": CLLocationCoordinate2D(latitude: 40.06055, longitude: -75.17861),
    "SEPR90510": CLLocationCoordinate2D(latitude: 40.04945, longitude: -75.40305),
    "SEPR90005": CLLocationCoordinate2D(latitude: 39.95389, longitude: -75.16778),
    "SEPR90305": CLLocationCoordinate2D(latitude: 39.90222, longitude: -75.35083),
    "SEPR90709": CLLocationCoordinate2D(latitude: 40.02333, longitude: -75.03889),
    "SEPR90007": CLLocationCoordinate2D(latitude: 39.98139, longitude: -75.14944),
    "SEPR90501": CLLocationCoordinate2D(latitude: 39.99278, longitude: -75.76361),
    "SEPR90707": CLLocationCoordinate2D(latitude: 40.05444, longitude: -74.98444),
    "SEPR90701": CLLocationCoordinate2D(latitude: 40.21851, longitude: -74.75393),
    "SEPR90322": CLLocationCoordinate2D(latitude: 40.14028, longitude: -74.9825),
    "SEPR90807": CLLocationCoordinate2D(latitude: 40.03528, longitude: -75.18694),
    "SEPR90806": CLLocationCoordinate2D(latitude: 40.0425, longitude: -75.19),
    "SEPR90514": CLLocationCoordinate2D(latitude: 40.03833, longitude: -75.34167),
    "SEPR90304": CLLocationCoordinate2D(latitude: 39.90361, longitude: -75.37194),
    "SEPR90417": CLLocationCoordinate2D(latitude: 40.19528, longitude: -75.08916),
    "SEPR90714": CLLocationCoordinate2D(latitude: 40.05083, longitude: -75.17139),
    "SEPR90300": CLLocationCoordinate2D(latitude: 39.90068, longitude: -75.45856),
    "SEPR90511": CLLocationCoordinate2D(latitude: 40.04583, longitude: -75.38667),
    "SEPR90009": CLLocationCoordinate2D(latitude: 40.02222, longitude: -75.16),
    "SEPR90327": CLLocationCoordinate2D(latitude: 40.25778, longitude: -74.81528),
    "SEPR90503": CLLocationCoordinate2D(latitude: 40.01472, longitude: -75.63805),
    "SEPR90415": CLLocationCoordinate2D(latitude: 40.14389, longitude: -75.11417),
    "SEPR90203": CLLocationCoordinate2D(latitude: 39.73726, longitude: -75.55109),
    "SEPR90220": CLLocationCoordinate2D(latitude: 40.01667, longitude: -75.21028),
    "SEPR90712": CLLocationCoordinate2D(latitude: 40.03611, longitude: -75.16111),
    "SEPR90325": CLLocationCoordinate2D(latitude: 40.1925, longitude: -74.88917),
    "SEPR90718": CLLocationCoordinate2D(latitude: 40.07333, longitude: -75.19666),
    "SEPR90003": CLLocationCoordinate2D(latitude: 39.99, longitude: -75.22556),
    "SEPR90519": CLLocationCoordinate2D(latitude: 40.00278, longitude: -75.2725),
    "SEPR90326": CLLocationCoordinate2D(latitude: 40.23528, longitude: -74.83056),

    // SEPTA Metro Stations
    "SEPM30866": CLLocationCoordinate2D(latitude: 39.920121, longitude: -75.263141),
    "SEPM20838": CLLocationCoordinate2D(latitude: 39.923621, longitude: -75.257349),
    "SEPM20841": CLLocationCoordinate2D(latitude: 39.921306, longitude: -75.261462),
    "SEPM20840": CLLocationCoordinate2D(latitude: 39.922553, longitude: -75.259641),
    "SEPM20839": CLLocationCoordinate2D(latitude: 39.923096, longitude: -75.258471),
    "SEPM2456": CLLocationCoordinate2D(latitude: 39.951729, longitude: -75.158322),
    "SEPM2455": CLLocationCoordinate2D(latitude: 39.952101, longitude: -75.16145),
    "SEPM283": CLLocationCoordinate2D(latitude: 39.952532, longitude: -75.162559),
    "SEPM1392": CLLocationCoordinate2D(latitude: 39.952609, longitude: -75.165286),
    "SEPM31140": CLLocationCoordinate2D(latitude: 39.952502, longitude: -75.165369),
    "SEPM20659": CLLocationCoordinate2D(latitude: 39.952672, longitude: -75.165345),
    "SEPM33029": CLLocationCoordinate2D(latitude: 39.952468, longitude: -75.164092),
    "SEPM1281": CLLocationCoordinate2D(latitude: 39.952468, longitude: -75.164094),
    "SEPM20646": CLLocationCoordinate2D(latitude: 39.953327, longitude: -75.171637),
    "SEPM20660": CLLocationCoordinate2D(latitude: 39.953425, longitude: -75.171483),
    "SEPM20645": CLLocationCoordinate2D(latitude: 39.953962, longitude: -75.176736),
    "SEPM20661": CLLocationCoordinate2D(latitude: 39.954051, longitude: -75.176571),
    "SEPM21072": CLLocationCoordinate2D(latitude: 39.972701, longitude: -75.179198),
    "SEPM428": CLLocationCoordinate2D(latitude: 39.949827, longitude: -75.143752),
    "SEPM20658": CLLocationCoordinate2D(latitude: 39.954871, longitude: -75.189499),
    "SEPM20642": CLLocationCoordinate2D(latitude: 39.954782, longitude: -75.189523),
    "SEPM2453": CLLocationCoordinate2D(latitude: 39.955866, longitude: -75.19148),
    "SEPM20665": CLLocationCoordinate2D(latitude: 39.958404, longitude: -75.193585),
    "SEPM20664": CLLocationCoordinate2D(latitude: 39.956058, longitude: -75.194113),
    "SEPM20640": CLLocationCoordinate2D(latitude: 39.956281, longitude: -75.194218),
    "SEPM20641": CLLocationCoordinate2D(latitude: 39.955335, longitude: -75.194162),
    "SEPM287": CLLocationCoordinate2D(latitude: 39.955451, longitude: -75.194233),
    "SEPM20733": CLLocationCoordinate2D(latitude: 39.95389, longitude: -75.194722),
    "SEPM20732": CLLocationCoordinate2D(latitude: 39.953854, longitude: -75.194533),
    "SEPM20731": CLLocationCoordinate2D(latitude: 39.950993, longitude: -75.196586),
    "SEPM20734": CLLocationCoordinate2D(latitude: 39.951048, longitude: -75.197306),
    "SEPM2452": CLLocationCoordinate2D(latitude: 39.957152, longitude: -75.201963),
    "SEPM21423": CLLocationCoordinate2D(latitude: 39.960464, longitude: -75.202177),
    "SEPM21425": CLLocationCoordinate2D(latitude: 39.955796, longitude: -75.202333),
    "SEPM279": CLLocationCoordinate2D(latitude: 39.957929, longitude: -75.201901),
    "SEPM22230": CLLocationCoordinate2D(latitude: 39.953075, longitude: -75.202885),
    "SEPM21424": CLLocationCoordinate2D(latitude: 39.959232, longitude: -75.202039),
    "SEPM21422": CLLocationCoordinate2D(latitude: 39.961705, longitude: -75.202314),
    "SEPM21426": CLLocationCoordinate2D(latitude: 39.954262, longitude: -75.202633),
    "SEPM20804": CLLocationCoordinate2D(latitude: 39.949533, longitude: -75.203333),
    "SEPM301": CLLocationCoordinate2D(latitude: 39.949595, longitude: -75.203333),
    "SEPM21248": CLLocationCoordinate2D(latitude: 39.957259, longitude: -75.202021),
    "SEPM30823": CLLocationCoordinate2D(latitude: 39.96005, longitude: -75.20526),
    "SEPM21465": CLLocationCoordinate2D(latitude: 39.962505, longitude: -75.205501),
    "SEPM567": CLLocationCoordinate2D(latitude: 39.964941, longitude: -75.205493),
    "SEPM351": CLLocationCoordinate2D(latitude: 39.958836, longitude: -75.205111),
    "SEPM364": CLLocationCoordinate2D(latitude: 39.961246, longitude: -75.205375),
    "SEPM21432": CLLocationCoordinate2D(latitude: 39.949879, longitude: -75.207241),
    "SEPM21456": CLLocationCoordinate2D(latitude: 39.949709, longitude: -75.207076),
    "SEPM21433": CLLocationCoordinate2D(latitude: 39.948594, longitude: -75.207174),
    "SEPM30820": CLLocationCoordinate2D(latitude: 39.951075, longitude: -75.207072),
    "SEPM21431": CLLocationCoordinate2D(latitude: 39.951253, longitude: -75.207189),
    "SEPM21457": CLLocationCoordinate2D(latitude: 39.952163, longitude: -75.206867),
    "SEPM2451": CLLocationCoordinate2D(latitude: 39.958655, longitude: -75.214028),
    "SEPM20897": CLLocationCoordinate2D(latitude: 39.93998, longitude: -75.211652),
    "SEPM20955": CLLocationCoordinate2D(latitude: 39.939819, longitude: -75.211286),
    "SEPM20957": CLLocationCoordinate2D(latitude: 39.940794, longitude: -75.212429),
    "SEPM2450": CLLocationCoordinate2D(latitude: 39.960003, longitude: -75.224907),
    "SEPM2449": CLLocationCoordinate2D(latitude: 39.961002, longitude: -75.232853),
    "SEPM2458": CLLocationCoordinate2D(latitude: 39.950565, longitude: -75.148939),
    "SEPM2448": CLLocationCoordinate2D(latitude: 39.961991, longitude: -75.240757),
    "SEPM20787": CLLocationCoordinate2D(latitude: 39.933632, longitude: -75.231399),
    "SEPM20823": CLLocationCoordinate2D(latitude: 39.932595, longitude: -75.230339),
    "SEPM599": CLLocationCoordinate2D(latitude: 39.943963, longitude: -75.246342),
    "SEPM2447": CLLocationCoordinate2D(latitude: 39.96275, longitude: -75.246767),
    "SEPM20695": CLLocationCoordinate2D(latitude: 39.980582, longitude: -75.246461),
    "SEPM20693": CLLocationCoordinate2D(latitude: 39.978234, longitude: -75.24603),
    "SEPM20612": CLLocationCoordinate2D(latitude: 39.97835, longitude: -75.246184),
    "SEPM20611": CLLocationCoordinate2D(latitude: 39.980912, longitude: -75.246661),
    "SEPM31294": CLLocationCoordinate2D(latitude: 39.983838, longitude: -75.245957),
    "SEPM20781": CLLocationCoordinate2D(latitude: 39.92905, longitude: -75.24108),
    "SEPM31218": CLLocationCoordinate2D(latitude: 39.929104, longitude: -75.240879),
    "SEPM20782": CLLocationCoordinate2D(latitude: 39.928628, longitude: -75.238897),
    "SEPM20827": CLLocationCoordinate2D(latitude: 39.92893, longitude: -75.238223),
    "SEPM20843": CLLocationCoordinate2D(latitude: 39.927902, longitude: -75.23714),
    "SEPM416": CLLocationCoordinate2D(latitude: 39.962577, longitude: -75.258867),
    "SEPM15497": CLLocationCoordinate2D(latitude: 39.96217, longitude: -75.259677),
    "SEPM612": CLLocationCoordinate2D(latitude: 39.898748, longitude: -75.23926),
    "SEPM2457": CLLocationCoordinate2D(latitude: 39.951138, longitude: -75.153589),
    "SEPM20772": CLLocationCoordinate2D(latitude: 39.922566, longitude: -75.255994),
    "SEPM32523": CLLocationCoordinate2D(latitude: 39.918924, longitude: -75.261845),
    "SEPM20768": CLLocationCoordinate2D(latitude: 39.919921, longitude: -75.260545),
    "SEPM20770": CLLocationCoordinate2D(latitude: 39.921142, longitude: -75.258866),
    "SEPM20771": CLLocationCoordinate2D(latitude: 39.92205, longitude: -75.257482),
    "SEPM18626": CLLocationCoordinate2D(latitude: 39.947826, longitude: -75.312636),
    "SEPM18603": CLLocationCoordinate2D(latitude: 39.94796, longitude: -75.312825),
    "SEPM15334": CLLocationCoordinate2D(latitude: 39.911684, longitude: -75.281832),
    "SEPM15333": CLLocationCoordinate2D(latitude: 39.911613, longitude: -75.281997),
    "SEPM1923": CLLocationCoordinate2D(latitude: 39.9999, longitude: -75.309449),
    "SEPM30519": CLLocationCoordinate2D(latitude: 39.996275, longitude: -75.303724),
    "SEPM16395": CLLocationCoordinate2D(latitude: 39.949203, longitude: -75.306033),
    "SEPM16402": CLLocationCoordinate2D(latitude: 39.949319, longitude: -75.306304),
    "SEPM217": CLLocationCoordinate2D(latitude: 40.016587, longitude: -75.083844),
    "SEPM1938": CLLocationCoordinate2D(latitude: 39.957649, longitude: -75.269301),
    "SEPM1957": CLLocationCoordinate2D(latitude: 39.95772, longitude: -75.268888),
    "SEPM30376": CLLocationCoordinate2D(latitude: 39.931313, longitude: -75.292841),
    "SEPM1959": CLLocationCoordinate2D(latitude: 39.931233, longitude: -75.292912),
    "SEPM20879": CLLocationCoordinate2D(latitude: 39.949861, longitude: -75.206945),
    "SEPM20876": CLLocationCoordinate2D(latitude: 39.949736, longitude: -75.207265),
    "SEPM20880": CLLocationCoordinate2D(latitude: 39.949641, longitude: -75.209154),
    "SEPM20875": CLLocationCoordinate2D(latitude: 39.949481, longitude: -75.20932),
    "SEPM20874": CLLocationCoordinate2D(latitude: 39.949181, longitude: -75.21127),
    "SEPM20881": CLLocationCoordinate2D(latitude: 39.949332, longitude: -75.211092),
    "SEPM20873": CLLocationCoordinate2D(latitude: 39.949006, longitude: -75.213018),
    "SEPM20882": CLLocationCoordinate2D(latitude: 39.949148, longitude: -75.212828),
    "SEPM20872": CLLocationCoordinate2D(latitude: 39.948786, longitude: -75.215061),
    "SEPM20883": CLLocationCoordinate2D(latitude: 39.948937, longitude: -75.214884),
    "SEPM20884": CLLocationCoordinate2D(latitude: 39.948691, longitude: -75.21701),
    "SEPM20871": CLLocationCoordinate2D(latitude: 39.94854, longitude: -75.217188),
    "SEPM20885": CLLocationCoordinate2D(latitude: 39.948472, longitude: -75.219101),
    "SEPM601": CLLocationCoordinate2D(latitude: 39.948261, longitude: -75.221109),
    "SEPM600": CLLocationCoordinate2D(latitude: 39.948101, longitude: -75.221404),
    "SEPM20886": CLLocationCoordinate2D(latitude: 39.948041, longitude: -75.223199),
    "SEPM20869": CLLocationCoordinate2D(latitude: 39.947872, longitude: -75.223377),
    "SEPM20887": CLLocationCoordinate2D(latitude: 39.94783, longitude: -75.225266),
    "SEPM20868": CLLocationCoordinate2D(latitude: 39.947715, longitude: -75.225456),
    "SEPM20888": CLLocationCoordinate2D(latitude: 39.947842, longitude: -75.227309),
    "SEPM20866": CLLocationCoordinate2D(latitude: 39.947766, longitude: -75.229612),
    "SEPM20889": CLLocationCoordinate2D(latitude: 39.947846, longitude: -75.229317),
    "SEPM20865": CLLocationCoordinate2D(latitude: 39.947742, longitude: -75.231466),
    "SEPM20890": CLLocationCoordinate2D(latitude: 39.947797, longitude: -75.232139),
    "SEPM20864": CLLocationCoordinate2D(latitude: 39.947246, longitude: -75.233746),
    "SEPM20891": CLLocationCoordinate2D(latitude: 39.947442, longitude: -75.233522),
    "SEPM20863": CLLocationCoordinate2D(latitude: 39.946785, longitude: -75.235602),
    "SEPM20892": CLLocationCoordinate2D(latitude: 39.946936, longitude: -75.235519),
    "SEPM20893": CLLocationCoordinate2D(latitude: 39.946431, longitude: -75.237763),
    "SEPM20862": CLLocationCoordinate2D(latitude: 39.946386, longitude: -75.237327),
    "SEPM20894": CLLocationCoordinate2D(latitude: 39.945988, longitude: -75.239937),
    "SEPM20861": CLLocationCoordinate2D(latitude: 39.945783, longitude: -75.240304),
    "SEPM20860": CLLocationCoordinate2D(latitude: 39.945197, longitude: -75.241899),
    "SEPM20895": CLLocationCoordinate2D(latitude: 39.945411, longitude: -75.241698),
    "SEPM20896": CLLocationCoordinate2D(latitude: 39.944468, longitude: -75.244322),
    "SEPM20859": CLLocationCoordinate2D(latitude: 39.944299, longitude: -75.244429),
    "SEPM20867": CLLocationCoordinate2D(latitude: 39.947727, longitude: -75.227912),
    "SEPM20870": CLLocationCoordinate2D(latitude: 39.948312, longitude: -75.219503),
    "SEPM4726": CLLocationCoordinate2D(latitude: 39.914605, longitude: -75.284222),
    "SEPM18842": CLLocationCoordinate2D(latitude: 39.914703, longitude: -75.284092),
    "SEPM18608": CLLocationCoordinate2D(latitude: 39.916249, longitude: -75.376967),
    "SEPM18620": CLLocationCoordinate2D(latitude: 39.916071, longitude: -75.376861),
    "SEPM1908": CLLocationCoordinate2D(latitude: 39.986517, longitude: -75.291466),
    "SEPM2460": CLLocationCoordinate2D(latitude: 39.978626, longitude: -75.133507),
    "SEPM18630": CLLocationCoordinate2D(latitude: 39.955326, longitude: -75.274066),
    "SEPM18599": CLLocationCoordinate2D(latitude: 39.955095, longitude: -75.274822),
    "SEPM1892": CLLocationCoordinate2D(latitude: 40.104955, longitude: -75.348141),
    "SEPM142": CLLocationCoordinate2D(latitude: 40.001589, longitude: -75.152875),
    "SEPM20966": CLLocationCoordinate2D(latitude: 39.971469, longitude: -75.15944),
    "SEPM1279": CLLocationCoordinate2D(latitude: 39.962383, longitude: -75.161429),
    "SEPM18606": CLLocationCoordinate2D(latitude: 39.933963, longitude: -75.32986),
    "SEPM18623": CLLocationCoordinate2D(latitude: 39.934409, longitude: -75.329458),
    "SEPM1925": CLLocationCoordinate2D(latitude: 40.018044, longitude: -75.323395),
    "SEPM1277": CLLocationCoordinate2D(latitude: 39.978668, longitude: -75.157883),
    "SEPM20802": CLLocationCoordinate2D(latitude: 39.948424, longitude: -75.207151),
    "SEPM20807": CLLocationCoordinate2D(latitude: 39.948549, longitude: -75.206879),
    "SEPM20801": CLLocationCoordinate2D(latitude: 39.948356, longitude: -75.209135),
    "SEPM20808": CLLocationCoordinate2D(latitude: 39.948481, longitude: -75.208945),
    "SEPM20800": CLLocationCoordinate2D(latitude: 39.9477, longitude: -75.211428),
    "SEPM20809": CLLocationCoordinate2D(latitude: 39.947878, longitude: -75.211403),
    "SEPM20799": CLLocationCoordinate2D(latitude: 39.946827, longitude: -75.212682),
    "SEPM20810": CLLocationCoordinate2D(latitude: 39.947006, longitude: -75.212658),
    "SEPM20811": CLLocationCoordinate2D(latitude: 39.94608, longitude: -75.213959),
    "SEPM20790": CLLocationCoordinate2D(latitude: 39.945901, longitude: -75.213984),
    "SEPM20812": CLLocationCoordinate2D(latitude: 39.945154, longitude: -75.215285),
    "SEPM20789": CLLocationCoordinate2D(latitude: 39.944958, longitude: -75.215344),
    "SEPM322": CLLocationCoordinate2D(latitude: 39.944281, longitude: -75.216527),
    "SEPM321": CLLocationCoordinate2D(latitude: 39.944041, longitude: -75.216622),
    "SEPM20797": CLLocationCoordinate2D(latitude: 39.942349, longitude: -75.219048),
    "SEPM20814": CLLocationCoordinate2D(latitude: 39.942519, longitude: -75.219012),
    "SEPM20796": CLLocationCoordinate2D(latitude: 39.941539, longitude: -75.220184),
    "SEPM20815": CLLocationCoordinate2D(latitude: 39.941726, longitude: -75.220124),
    "SEPM20816": CLLocationCoordinate2D(latitude: 39.940764, longitude: -75.221485),
    "SEPM20795": CLLocationCoordinate2D(latitude: 39.940577, longitude: -75.221556),
    "SEPM20817": CLLocationCoordinate2D(latitude: 39.939785, longitude: -75.222893),
    "SEPM20794": CLLocationCoordinate2D(latitude: 39.939607, longitude: -75.222952),
    "SEPM20818": CLLocationCoordinate2D(latitude: 39.938832, longitude: -75.224253),
    "SEPM20793": CLLocationCoordinate2D(latitude: 39.938654, longitude: -75.224301),
    "SEPM20792": CLLocationCoordinate2D(latitude: 39.937701, longitude: -75.225661),
    "SEPM20819": CLLocationCoordinate2D(latitude: 39.937871, longitude: -75.225625),
    "SEPM20820": CLLocationCoordinate2D(latitude: 39.936802, longitude: -75.227163),
    "SEPM20791": CLLocationCoordinate2D(latitude: 39.936642, longitude: -75.227187),
    "SEPM323": CLLocationCoordinate2D(latitude: 39.935832, longitude: -75.2285),
    "SEPM320": CLLocationCoordinate2D(latitude: 39.935653, longitude: -75.228572),
    "SEPM20788": CLLocationCoordinate2D(latitude: 39.934754, longitude: -75.229944),
    "SEPM20821": CLLocationCoordinate2D(latitude: 39.93495, longitude: -75.229849),
    "SEPM20822": CLLocationCoordinate2D(latitude: 39.933784, longitude: -75.231469),
    "SEPM20779": CLLocationCoordinate2D(latitude: 39.929359, longitude: -75.244762),
    "SEPM21209": CLLocationCoordinate2D(latitude: 39.929565, longitude: -75.244703),
    "SEPM20773": CLLocationCoordinate2D(latitude: 39.923697, longitude: -75.254279),
    "SEPM20835": CLLocationCoordinate2D(latitude: 39.923875, longitude: -75.254161),
    "SEPM20836": CLLocationCoordinate2D(latitude: 39.923012, longitude: -75.255946),
    "SEPM20778": CLLocationCoordinate2D(latitude: 39.92631, longitude: -75.246565),
    "SEPM20831": CLLocationCoordinate2D(latitude: 39.926577, longitude: -75.246044),
    "SEPM20833": CLLocationCoordinate2D(latitude: 39.92576, longitude: -75.249045),
    "SEPM20776": CLLocationCoordinate2D(latitude: 39.925617, longitude: -75.249175),
    "SEPM20775": CLLocationCoordinate2D(latitude: 39.925102, longitude: -75.250817),
    "SEPM20834": CLLocationCoordinate2D(latitude: 39.925245, longitude: -75.250699),
    "SEPM20777": CLLocationCoordinate2D(latitude: 39.92607, longitude: -75.247486),
    "SEPM30865": CLLocationCoordinate2D(latitude: 39.926213, longitude: -75.247368),
    "SEPM20431": CLLocationCoordinate2D(latitude: 39.906673, longitude: -75.278314),
    "SEPM2440": CLLocationCoordinate2D(latitude: 39.955027, longitude: -75.152748),
    "SEPM2464": CLLocationCoordinate2D(latitude: 40.010919, longitude: -75.088705),
    "SEPM18636": CLLocationCoordinate2D(latitude: 39.925723, longitude: -75.290161),
    "SEPM30374": CLLocationCoordinate2D(latitude: 39.92575, longitude: -75.289984),
    "SEPM21075": CLLocationCoordinate2D(latitude: 39.97239, longitude: -75.175384),
    "SEPM15344": CLLocationCoordinate2D(latitude: 39.952976, longitude: -75.279078),
    "SEPM15322": CLLocationCoordinate2D(latitude: 39.953092, longitude: -75.279101),
    "SEPM1931": CLLocationCoordinate2D(latitude: 40.05009, longitude: -75.347383),
    "SEPM15339": CLLocationCoordinate2D(latitude: 39.9351, longitude: -75.295136),
    "SEPM15328": CLLocationCoordinate2D(latitude: 39.9351, longitude: -75.295278),
    "SEPM305": CLLocationCoordinate2D(latitude: 39.919085, longitude: -75.262376),
    "SEPM1935": CLLocationCoordinate2D(latitude: 40.098759, longitude: -75.352066),
    "SEPM1940": CLLocationCoordinate2D(latitude: 39.947092, longitude: -75.292764),
    "SEPM1955": CLLocationCoordinate2D(latitude: 39.947012, longitude: -75.292575),
    "SEPM18846": CLLocationCoordinate2D(latitude: 39.942196, longitude: -75.296446),
    "SEPM15326": CLLocationCoordinate2D(latitude: 39.942205, longitude: -75.296611),
    "SEPM18600": CLLocationCoordinate2D(latitude: 39.949915, longitude: -75.286772),
    "SEPM18629": CLLocationCoordinate2D(latitude: 39.949709, longitude: -75.286949),
    "SEPM21532": CLLocationCoordinate2D(latitude: 39.95485, longitude: -75.183264),
    "SEPM20643": CLLocationCoordinate2D(latitude: 39.954815, longitude: -75.1835),
    "SEPM20662": CLLocationCoordinate2D(latitude: 39.954894, longitude: -75.183169),
    "SEPM18604": CLLocationCoordinate2D(latitude: 39.94724, longitude: -75.316144),
    "SEPM18625": CLLocationCoordinate2D(latitude: 39.947106, longitude: -75.315955),
    "SEPM18624": CLLocationCoordinate2D(latitude: 39.944559, longitude: -75.321592),
    "SEPM18605": CLLocationCoordinate2D(latitude: 39.944666, longitude: -75.321757),
    "SEPM18618": CLLocationCoordinate2D(latitude: 39.917333, longitude: -75.385772),
    "SEPM18610": CLLocationCoordinate2D(latitude: 39.917467, longitude: -75.385524),
    "SEPM1284": CLLocationCoordinate2D(latitude: 39.936177, longitude: -75.167129),
    "SEPM20902": CLLocationCoordinate2D(latitude: 39.931173, longitude: -75.217711),
    "SEPM20949": CLLocationCoordinate2D(latitude: 39.930986, longitude: -75.217747),
    "SEPM20948": CLLocationCoordinate2D(latitude: 39.929935, longitude: -75.219226),
    "SEPM20903": CLLocationCoordinate2D(latitude: 39.930131, longitude: -75.219202),
    "SEPM20947": CLLocationCoordinate2D(latitude: 39.928964, longitude: -75.220586),
    "SEPM20904": CLLocationCoordinate2D(latitude: 39.929152, longitude: -75.220539),
    "SEPM20946": CLLocationCoordinate2D(latitude: 39.928039, longitude: -75.221994),
    "SEPM20905": CLLocationCoordinate2D(latitude: 39.928226, longitude: -75.221958),
    "SEPM20907": CLLocationCoordinate2D(latitude: 39.926241, longitude: -75.224844),
    "SEPM20944": CLLocationCoordinate2D(latitude: 39.926044, longitude: -75.224868),
    "SEPM20908": CLLocationCoordinate2D(latitude: 39.925065, longitude: -75.226441),
    "SEPM20943": CLLocationCoordinate2D(latitude: 39.924842, longitude: -75.22656),
    "SEPM20942": CLLocationCoordinate2D(latitude: 39.923934, longitude: -75.227778),
    "SEPM20909": CLLocationCoordinate2D(latitude: 39.924157, longitude: -75.227671),
    "SEPM20910": CLLocationCoordinate2D(latitude: 39.923204, longitude: -75.229067),
    "SEPM20941": CLLocationCoordinate2D(latitude: 39.922972, longitude: -75.229126),
    "SEPM20940": CLLocationCoordinate2D(latitude: 39.922082, longitude: -75.230404),
    "SEPM20911": CLLocationCoordinate2D(latitude: 39.922305, longitude: -75.230285),
    "SEPM20912": CLLocationCoordinate2D(latitude: 39.921432, longitude: -75.231562),
    "SEPM20939": CLLocationCoordinate2D(latitude: 39.921236, longitude: -75.231587),
    "SEPM20913": CLLocationCoordinate2D(latitude: 39.920524, longitude: -75.23284),
    "SEPM20938": CLLocationCoordinate2D(latitude: 39.920327, longitude: -75.232911),
    "SEPM20914": CLLocationCoordinate2D(latitude: 39.919446, longitude: -75.234401),
    "SEPM20937": CLLocationCoordinate2D(latitude: 39.91925, longitude: -75.234425),
    "SEPM20915": CLLocationCoordinate2D(latitude: 39.918297, longitude: -75.236056),
    "SEPM20936": CLLocationCoordinate2D(latitude: 39.918101, longitude: -75.236081),
    "SEPM20935": CLLocationCoordinate2D(latitude: 39.91713, longitude: -75.237452),
    "SEPM20916": CLLocationCoordinate2D(latitude: 39.917327, longitude: -75.237428),
    "SEPM20917": CLLocationCoordinate2D(latitude: 39.916249, longitude: -75.238965),
    "SEPM20934": CLLocationCoordinate2D(latitude: 39.91608, longitude: -75.239013),
    "SEPM20918": CLLocationCoordinate2D(latitude: 39.915305, longitude: -75.240349),
    "SEPM20933": CLLocationCoordinate2D(latitude: 39.9151, longitude: -75.240408),
    "SEPM20932": CLLocationCoordinate2D(latitude: 39.914129, longitude: -75.241816),
    "SEPM610": CLLocationCoordinate2D(latitude: 39.914335, longitude: -75.241732),
    "SEPM20906": CLLocationCoordinate2D(latitude: 39.926935, longitude: -75.22385),
    "SEPM20919": CLLocationCoordinate2D(latitude: 39.913284, longitude: -75.243092),
    "SEPM20931": CLLocationCoordinate2D(latitude: 39.913266, longitude: -75.242998),
    "SEPM611": CLLocationCoordinate2D(latitude: 39.914015, longitude: -75.242642),
    "SEPM140": CLLocationCoordinate2D(latitude: 40.009234, longitude: -75.151203),
    "SEPM838": CLLocationCoordinate2D(latitude: 40.005857, longitude: -75.096434),
    "SEPM15319": CLLocationCoordinate2D(latitude: 39.960882, longitude: -75.263743),
    "SEPM15348": CLLocationCoordinate2D(latitude: 39.960864, longitude: -75.263613),
    "SEPM1278": CLLocationCoordinate2D(latitude: 39.967034, longitude: -75.16042),
    "SEPM20965": CLLocationCoordinate2D(latitude: 40.04185, longitude: -75.136757),
    "SEPM31347": CLLocationCoordinate2D(latitude: 39.964945, longitude: -75.134154),
    "SEPM481": CLLocationCoordinate2D(latitude: 39.968774, longitude: -75.134351),
    "SEPM31540": CLLocationCoordinate2D(latitude: 39.96865, longitude: -75.134493),
    "SEPM23992": CLLocationCoordinate2D(latitude: 39.966008, longitude: -75.134338),
    "SEPM24038": CLLocationCoordinate2D(latitude: 39.966124, longitude: -75.134492),
    "SEPM61": CLLocationCoordinate2D(latitude: 40.022996, longitude: -75.07795),
    "SEPM353": CLLocationCoordinate2D(latitude: 39.968886, longitude: -75.136199),
    "SEPM1927": CLLocationCoordinate2D(latitude: 40.027961, longitude: -75.336408),
    "SEPM15341": CLLocationCoordinate2D(latitude: 39.944088, longitude: -75.295781),
    "SEPM15325": CLLocationCoordinate2D(latitude: 39.944052, longitude: -75.295958),
    "SEPM21001": CLLocationCoordinate2D(latitude: 39.970845, longitude: -75.154021),
    "SEPM21087": CLLocationCoordinate2D(latitude: 39.970756, longitude: -75.154222),
    "SEPM21086": CLLocationCoordinate2D(latitude: 39.970965, longitude: -75.155816),
    "SEPM21002": CLLocationCoordinate2D(latitude: 39.971045, longitude: -75.155603),
    "SEPM21083": CLLocationCoordinate2D(latitude: 39.971828, longitude: -75.162806),
    "SEPM21005": CLLocationCoordinate2D(latitude: 39.971908, longitude: -75.162605),
    "SEPM21082": CLLocationCoordinate2D(latitude: 39.972028, longitude: -75.164352),
    "SEPM21006": CLLocationCoordinate2D(latitude: 39.972116, longitude: -75.164151),
    "SEPM21080": CLLocationCoordinate2D(latitude: 39.972427, longitude: -75.16754),
    "SEPM30290": CLLocationCoordinate2D(latitude: 39.972507, longitude: -75.167339),
    "SEPM21009": CLLocationCoordinate2D(latitude: 39.972715, longitude: -75.168874),
    "SEPM21079": CLLocationCoordinate2D(latitude: 39.972636, longitude: -75.169087),
    "SEPM30791": CLLocationCoordinate2D(latitude: 39.972453, longitude: -75.175844),
    "SEPM21071": CLLocationCoordinate2D(latitude: 39.973896, longitude: -75.178946),
    "SEPM21016": CLLocationCoordinate2D(latitude: 39.973976, longitude: -75.178733),
    "SEPM21070": CLLocationCoordinate2D(latitude: 39.974113, longitude: -75.180504),
    "SEPM21017": CLLocationCoordinate2D(latitude: 39.974202, longitude: -75.18028),
    "SEPM21069": CLLocationCoordinate2D(latitude: 39.974286, longitude: -75.181969),
    "SEPM21018": CLLocationCoordinate2D(latitude: 39.974375, longitude: -75.181756),
    "SEPM21068": CLLocationCoordinate2D(latitude: 39.974486, longitude: -75.183622),
    "SEPM21019": CLLocationCoordinate2D(latitude: 39.974574, longitude: -75.183361),
    "SEPM20993": CLLocationCoordinate2D(latitude: 39.9695, longitude: -75.13945),
    "SEPM21096": CLLocationCoordinate2D(latitude: 39.969439, longitude: -75.139805),
    "SEPM21067": CLLocationCoordinate2D(latitude: 39.974938, longitude: -75.18675),
    "SEPM21021": CLLocationCoordinate2D(latitude: 39.975009, longitude: -75.186549),
    "SEPM21022": CLLocationCoordinate2D(latitude: 39.975199, longitude: -75.188002),
    "SEPM30292": CLLocationCoordinate2D(latitude: 39.974841, longitude: -75.196733),
    "SEPM30291": CLLocationCoordinate2D(latitude: 39.975126, longitude: -75.196472),
    "SEPM21063": CLLocationCoordinate2D(latitude: 39.974297, longitude: -75.201802),
    "SEPM21025": CLLocationCoordinate2D(latitude: 39.974511, longitude: -75.201683),
    "SEPM21095": CLLocationCoordinate2D(latitude: 39.969711, longitude: -75.141599),
    "SEPM20994": CLLocationCoordinate2D(latitude: 39.969799, longitude: -75.141386),
    "SEPM350": CLLocationCoordinate2D(latitude: 39.974043, longitude: -75.204531),
    "SEPM344": CLLocationCoordinate2D(latitude: 39.974159, longitude: -75.204543),
    "SEPM21026": CLLocationCoordinate2D(latitude: 39.973966, longitude: -75.206268),
    "SEPM21062": CLLocationCoordinate2D(latitude: 39.973823, longitude: -75.206528),
    "SEPM21061": CLLocationCoordinate2D(latitude: 39.973542, longitude: -75.208975),
    "SEPM21027": CLLocationCoordinate2D(latitude: 39.973658, longitude: -75.208797),
    "SEPM21030": CLLocationCoordinate2D(latitude: 39.972917, longitude: -75.219064),
    "SEPM20995": CLLocationCoordinate2D(latitude: 39.96999, longitude: -75.142968),
    "SEPM21032": CLLocationCoordinate2D(latitude: 39.971987, longitude: -75.223438),
    "SEPM21056": CLLocationCoordinate2D(latitude: 39.971845, longitude: -75.223745),
    "SEPM21033": CLLocationCoordinate2D(latitude: 39.971473, longitude: -75.22579),
    "SEPM21055": CLLocationCoordinate2D(latitude: 39.971357, longitude: -75.225908),
    "SEPM21053": CLLocationCoordinate2D(latitude: 39.971041, longitude: -75.228803),
    "SEPM21035": CLLocationCoordinate2D(latitude: 39.971165, longitude: -75.228614),
    "SEPM21051": CLLocationCoordinate2D(latitude: 39.970636, longitude: -75.232667),
    "SEPM21037": CLLocationCoordinate2D(latitude: 39.970761, longitude: -75.232477),
    "SEPM21050": CLLocationCoordinate2D(latitude: 39.97046, longitude: -75.234285),
    "SEPM21038": CLLocationCoordinate2D(latitude: 39.970585, longitude: -75.234096),
    "SEPM345": CLLocationCoordinate2D(latitude: 39.970224, longitude: -75.237334),
    "SEPM349": CLLocationCoordinate2D(latitude: 39.970099, longitude: -75.237523),
    "SEPM21093": CLLocationCoordinate2D(latitude: 39.970129, longitude: -75.145094),
    "SEPM20996": CLLocationCoordinate2D(latitude: 39.970218, longitude: -75.144905),
    "SEPM21040": CLLocationCoordinate2D(latitude: 39.970039, longitude: -75.238988),
    "SEPM21048": CLLocationCoordinate2D(latitude: 39.969897, longitude: -75.239366),
    "SEPM21047": CLLocationCoordinate2D(latitude: 39.969801, longitude: -75.241221),
    "SEPM31443": CLLocationCoordinate2D(latitude: 39.970063, longitude: -75.243216),
    "SEPM21044": CLLocationCoordinate2D(latitude: 39.970226, longitude: -75.244598),
    "SEPM20998": CLLocationCoordinate2D(latitude: 39.970484, longitude: -75.148022),
    "SEPM21091": CLLocationCoordinate2D(latitude: 39.970386, longitude: -75.148211),
    "SEPM21090": CLLocationCoordinate2D(latitude: 39.97047, longitude: -75.150042),
    "SEPM20999": CLLocationCoordinate2D(latitude: 39.970568, longitude: -75.149853),
    "SEPM21028": CLLocationCoordinate2D(latitude: 39.973315, longitude: -75.212094),
    "SEPM21060": CLLocationCoordinate2D(latitude: 39.973208, longitude: -75.211964),
    "SEPM20986": CLLocationCoordinate2D(latitude: 39.971869, longitude: -75.125833),
    "SEPM21103": CLLocationCoordinate2D(latitude: 39.971709, longitude: -75.125999),
    "SEPM343": CLLocationCoordinate2D(latitude: 39.971499, longitude: -75.159275),
    "SEPM352": CLLocationCoordinate2D(latitude: 39.971428, longitude: -75.159594),
    "SEPM20989": CLLocationCoordinate2D(latitude: 39.970265, longitude: -75.130423),
    "SEPM21100": CLLocationCoordinate2D(latitude: 39.970122, longitude: -75.130542),
    "SEPM21078": CLLocationCoordinate2D(latitude: 39.972817, longitude: -75.170421),
    "SEPM21010": CLLocationCoordinate2D(latitude: 39.972888, longitude: -75.17022),
    "SEPM20991": CLLocationCoordinate2D(latitude: 39.968891, longitude: -75.134397),
    "SEPM21098": CLLocationCoordinate2D(latitude: 39.968855, longitude: -75.134244),
    "SEPM342": CLLocationCoordinate2D(latitude: 39.968903, longitude: -75.136075),
    "SEPM20978": CLLocationCoordinate2D(latitude: 39.968851, longitude: -75.136358),
    "SEPM21058": CLLocationCoordinate2D(latitude: 39.972978, longitude: -75.218521),
    "SEPM30550": CLLocationCoordinate2D(latitude: 39.972814, longitude: -75.216277),
    "SEPM30605": CLLocationCoordinate2D(latitude: 39.972725, longitude: -75.216431),
    "SEPM21101": CLLocationCoordinate2D(latitude: 39.97084, longitude: -75.128519),
    "SEPM20988": CLLocationCoordinate2D(latitude: 39.970983, longitude: -75.1284),
    "SEPM21105": CLLocationCoordinate2D(latitude: 39.972988, longitude: -75.119769),
    "SEPM21008": CLLocationCoordinate2D(latitude: 39.97238, longitude: -75.166217),
    "SEPM21081": CLLocationCoordinate2D(latitude: 39.972309, longitude: -75.166572),
    "SEPM20954": CLLocationCoordinate2D(latitude: 39.936991, longitude: -75.212251),
    "SEPM30595": CLLocationCoordinate2D(latitude: 39.937188, longitude: -75.212227),
    "SEPM20899": CLLocationCoordinate2D(latitude: 39.936128, longitude: -75.213682),
    "SEPM1895": CLLocationCoordinate2D(latitude: 40.070861, longitude: -75.342337),
    "SEPM21041": CLLocationCoordinate2D(latitude: 39.970899, longitude: -75.240781),
    "SEPM21042": CLLocationCoordinate2D(latitude: 39.971642, longitude: -75.242704),
    "SEPM21481": CLLocationCoordinate2D(latitude: 39.971895, longitude: -75.244641),
    "SEPM1924": CLLocationCoordinate2D(latitude: 40.009799, longitude: -75.31514),
    "SEPM18631": CLLocationCoordinate2D(latitude: 39.955967, longitude: -75.272718),
    "SEPM18598": CLLocationCoordinate2D(latitude: 39.955896, longitude: -75.273131),
    "SEPM15349": CLLocationCoordinate2D(latitude: 39.947597, longitude: -75.29764),
    "SEPM15376": CLLocationCoordinate2D(latitude: 39.94741, longitude: -75.297688),
    "SEPM1934": CLLocationCoordinate2D(latitude: 40.081526, longitude: -75.349127),
    "SEPM1274": CLLocationCoordinate2D(latitude: 40.016933, longitude: -75.149529),
    "SEPM2462": CLLocationCoordinate2D(latitude: 39.988834, longitude: -75.127303),
    "SEPM18601": CLLocationCoordinate2D(latitude: 39.948864, longitude: -75.288982),
    "SEPM18628": CLLocationCoordinate2D(latitude: 39.948668, longitude: -75.289148),
    "SEPM20927": CLLocationCoordinate2D(latitude: 39.904257, longitude: -75.240461),
    "SEPM20923": CLLocationCoordinate2D(latitude: 39.903855, longitude: -75.240403),
    "SEPM24738": CLLocationCoordinate2D(latitude: 39.899525, longitude: -75.239352),
    "SEPM605": CLLocationCoordinate2D(latitude: 39.899471, longitude: -75.23927),
    "SEPM20921": CLLocationCoordinate2D(latitude: 39.909132, longitude: -75.2421),
    "SEPM20929": CLLocationCoordinate2D(latitude: 39.90915, longitude: -75.242029),
    "SEPM18611": CLLocationCoordinate2D(latitude: 39.917985, longitude: -75.389348),
    "SEPM18617": CLLocationCoordinate2D(latitude: 39.917843, longitude: -75.389584),
    "SEPM60": CLLocationCoordinate2D(latitude: 39.996502, longitude: -75.11347),
    "SEPM20786": CLLocationCoordinate2D(latitude: 39.932479, longitude: -75.230316),
    "SEPM20824": CLLocationCoordinate2D(latitude: 39.93125, longitude: -75.232291),
    "SEPM20784": CLLocationCoordinate2D(latitude: 39.931045, longitude: -75.232386),
    "SEPM20825": CLLocationCoordinate2D(latitude: 39.9302, longitude: -75.233793),
    "SEPM20785": CLLocationCoordinate2D(latitude: 39.929994, longitude: -75.233888),
    "SEPM20826": CLLocationCoordinate2D(latitude: 39.927982, longitude: -75.236963),
    "SEPM20639": CLLocationCoordinate2D(latitude: 39.958565, longitude: -75.193786),
    "SEPM20638": CLLocationCoordinate2D(latitude: 39.960267, longitude: -75.197016),
    "SEPM20663": CLLocationCoordinate2D(latitude: 39.96024, longitude: -75.196721),
    "SEPM20635": CLLocationCoordinate2D(latitude: 39.963151, longitude: -75.20244),
    "SEPM20671": CLLocationCoordinate2D(latitude: 39.965102, longitude: -75.205386),
    "SEPM20634": CLLocationCoordinate2D(latitude: 39.965093, longitude: -75.205564),
    "SEPM20633": CLLocationCoordinate2D(latitude: 39.966391, longitude: -75.207662),
    "SEPM20672": CLLocationCoordinate2D(latitude: 39.966399, longitude: -75.207485),
    "SEPM20632": CLLocationCoordinate2D(latitude: 39.967725, longitude: -75.209878),
    "SEPM20631": CLLocationCoordinate2D(latitude: 39.968772, longitude: -75.211541),
    "SEPM20630": CLLocationCoordinate2D(latitude: 39.969667, longitude: -75.212991),
    "SEPM20628": CLLocationCoordinate2D(latitude: 39.971555, longitude: -75.216115),
    "SEPM20677": CLLocationCoordinate2D(latitude: 39.971564, longitude: -75.215938),
    "SEPM290": CLLocationCoordinate2D(latitude: 39.972244, longitude: -75.217035),
    "SEPM20678": CLLocationCoordinate2D(latitude: 39.973703, longitude: -75.219464),
    "SEPM20626": CLLocationCoordinate2D(latitude: 39.975207, longitude: -75.22259),
    "SEPM20679": CLLocationCoordinate2D(latitude: 39.975234, longitude: -75.222389),
    "SEPM20681": CLLocationCoordinate2D(latitude: 39.977186, longitude: -75.2266),
    "SEPM20625": CLLocationCoordinate2D(latitude: 39.976855, longitude: -75.226176),
    "SEPM277": CLLocationCoordinate2D(latitude: 39.973059, longitude: -75.218615),
    "SEPM20669": CLLocationCoordinate2D(latitude: 39.9629, longitude: -75.201826),
    "SEPM20674": CLLocationCoordinate2D(latitude: 39.968565, longitude: -75.210998),
    "SEPM20673": CLLocationCoordinate2D(latitude: 39.96767, longitude: -75.20956),
    "SEPM32722": CLLocationCoordinate2D(latitude: 39.959774, longitude: -75.19612),
    "SEPM31488": CLLocationCoordinate2D(latitude: 39.959631, longitude: -75.195542),
    "SEPM20636": CLLocationCoordinate2D(latitude: 39.962004, longitude: -75.200353),
    "SEPM20668": CLLocationCoordinate2D(latitude: 39.961923, longitude: -75.199952),
    "SEPM20627": CLLocationCoordinate2D(latitude: 39.973748, longitude: -75.219747),
    "SEPM20670": CLLocationCoordinate2D(latitude: 39.963857, longitude: -75.203371),
    "SEPM20675": CLLocationCoordinate2D(latitude: 39.969353, longitude: -75.212283),
    "SEPM30494": CLLocationCoordinate2D(latitude: 39.951614, longitude: -75.282328),
    "SEPM1939": CLLocationCoordinate2D(latitude: 39.951694, longitude: -75.282422),
    "SEPM20623": CLLocationCoordinate2D(latitude: 39.977013, longitude: -75.229908),
    "SEPM20683": CLLocationCoordinate2D(latitude: 39.977129, longitude: -75.229755),
    "SEPM20622": CLLocationCoordinate2D(latitude: 39.976811, longitude: -75.231858),
    "SEPM20684": CLLocationCoordinate2D(latitude: 39.976927, longitude: -75.231704),
    "SEPM20619": CLLocationCoordinate2D(latitude: 39.976591, longitude: -75.233761),
    "SEPM20685": CLLocationCoordinate2D(latitude: 39.976707, longitude: -75.233607),
    "SEPM20618": CLLocationCoordinate2D(latitude: 39.976406, longitude: -75.235403),
    "SEPM20686": CLLocationCoordinate2D(latitude: 39.976522, longitude: -75.235249),
    "SEPM20617": CLLocationCoordinate2D(latitude: 39.976248, longitude: -75.236904),
    "SEPM20687": CLLocationCoordinate2D(latitude: 39.976363, longitude: -75.23675),
    "SEPM20688": CLLocationCoordinate2D(latitude: 39.97617, longitude: -75.238499),
    "SEPM20616": CLLocationCoordinate2D(latitude: 39.976054, longitude: -75.238653),
    "SEPM15271": CLLocationCoordinate2D(latitude: 39.975851, longitude: -75.240378),
    "SEPM20689": CLLocationCoordinate2D(latitude: 39.975976, longitude: -75.240153),
    "SEPM20615": CLLocationCoordinate2D(latitude: 39.975693, longitude: -75.241879),
    "SEPM20690": CLLocationCoordinate2D(latitude: 39.975809, longitude: -75.241725),
    "SEPM20614": CLLocationCoordinate2D(latitude: 39.975499, longitude: -75.243651),
    "SEPM20691": CLLocationCoordinate2D(latitude: 39.975615, longitude: -75.243497),
    "SEPM20613": CLLocationCoordinate2D(latitude: 39.975332, longitude: -75.244986),
    "SEPM20692": CLLocationCoordinate2D(latitude: 39.975404, longitude: -75.245435),
    "SEPM20624": CLLocationCoordinate2D(latitude: 39.977295, longitude: -75.227451),
    "SEPM18614": CLLocationCoordinate2D(latitude: 39.926338, longitude: -75.337378),
    "SEPM18622": CLLocationCoordinate2D(latitude: 39.926267, longitude: -75.337154),
    "SEPM20952": CLLocationCoordinate2D(latitude: 39.935121, longitude: -75.214358),
    "SEPM20901": CLLocationCoordinate2D(latitude: 39.933588, longitude: -75.215579),
    "SEPM20951": CLLocationCoordinate2D(latitude: 39.9334, longitude: -75.215532),
    "SEPM20900": CLLocationCoordinate2D(latitude: 39.935282, longitude: -75.214429),
    "SEPM20950": CLLocationCoordinate2D(latitude: 39.932402, longitude: -75.216232),
    "SEPM1272": CLLocationCoordinate2D(latitude: 40.030617, longitude: -75.146533),
    "SEPM1283": CLLocationCoordinate2D(latitude: 39.944073, longitude: -75.165424),
    "SEPM2099": CLLocationCoordinate2D(latitude: 39.910255, longitude: -75.280973),
    "SEPM29523": CLLocationCoordinate2D(latitude: 39.910282, longitude: -75.280832),
    "SEPM18843": CLLocationCoordinate2D(latitude: 39.919419, longitude: -75.28675),
    "SEPM10011": CLLocationCoordinate2D(latitude: 39.919517, longitude: -75.287045),
    "SEPM20762": CLLocationCoordinate2D(latitude: 39.916614, longitude: -75.250319),
    "SEPM20702": CLLocationCoordinate2D(latitude: 39.916579, longitude: -75.250567),
    "SEPM20701": CLLocationCoordinate2D(latitude: 39.916866, longitude: -75.251841),
    "SEPM20763": CLLocationCoordinate2D(latitude: 39.916892, longitude: -75.251534),
    "SEPM20700": CLLocationCoordinate2D(latitude: 39.917144, longitude: -75.253044),
    "SEPM20764": CLLocationCoordinate2D(latitude: 39.917171, longitude: -75.252737),
    "SEPM20765": CLLocationCoordinate2D(latitude: 39.91753, longitude: -75.254295),
    "SEPM20699": CLLocationCoordinate2D(latitude: 39.917504, longitude: -75.254613),
    "SEPM20698": CLLocationCoordinate2D(latitude: 39.917791, longitude: -75.255852),
    "SEPM20766": CLLocationCoordinate2D(latitude: 39.917808, longitude: -75.255486),
    "SEPM20761": CLLocationCoordinate2D(latitude: 39.916451, longitude: -75.248915),
    "SEPM20703": CLLocationCoordinate2D(latitude: 39.916363, longitude: -75.24921),
    "SEPM24568": CLLocationCoordinate2D(latitude: 39.918091, longitude: -75.260053),
    "SEPM25241": CLLocationCoordinate2D(latitude: 39.918244, longitude: -75.260608),
    "SEPM20697": CLLocationCoordinate2D(latitude: 39.918088, longitude: -75.257315),
    "SEPM20767": CLLocationCoordinate2D(latitude: 39.91815, longitude: -75.25709),
    "SEPM20610": CLLocationCoordinate2D(latitude: 39.983697, longitude: -75.247009),
    "SEPM18609": CLLocationCoordinate2D(latitude: 39.917055, longitude: -75.382738),
    "SEPM18619": CLLocationCoordinate2D(latitude: 39.91693, longitude: -75.382998),
    "SEPM15327": CLLocationCoordinate2D(latitude: 39.940135, longitude: -75.296544),
    "SEPM15340": CLLocationCoordinate2D(latitude: 39.94017, longitude: -75.296378),
    "SEPM1932": CLLocationCoordinate2D(latitude: 40.058188, longitude: -75.339455),
    "SEPM2446": CLLocationCoordinate2D(latitude: 39.964355, longitude: -75.252243),
    "SEPM15380": CLLocationCoordinate2D(latitude: 39.917592, longitude: -75.387766),
    "SEPM15379": CLLocationCoordinate2D(latitude: 39.917726, longitude: -75.387518),
    "SEPM324": CLLocationCoordinate2D(latitude: 39.929069, longitude: -75.235413),
    "SEPM319": CLLocationCoordinate2D(latitude: 39.92889, longitude: -75.235461),
    "SEPM152": CLLocationCoordinate2D(latitude: 39.905428, longitude: -75.173857),
    "SEPM30520": CLLocationCoordinate2D(latitude: 40.113468, longitude: -75.345161),
    "SEPM2439": CLLocationCoordinate2D(latitude: 39.993939, longitude: -75.154588),
    "SEPM1964": CLLocationCoordinate2D(latitude: 39.917596, longitude: -75.285408),
    "SEPM1961": CLLocationCoordinate2D(latitude: 39.917498, longitude: -75.28555),
    "SEPM18616": CLLocationCoordinate2D(latitude: 39.918066, longitude: -75.391165),
    "SEPM18612": CLLocationCoordinate2D(latitude: 39.9182, longitude: -75.390917),
    "SEPM33027": CLLocationCoordinate2D(latitude: 40.039057, longitude: -75.144732),
    "SEPM82": CLLocationCoordinate2D(latitude: 40.039052, longitude: -75.144713),
    "SEPM1948": CLLocationCoordinate2D(latitude: 39.918478, longitude: -75.393998),
    "SEPM1947": CLLocationCoordinate2D(latitude: 39.918629, longitude: -75.393939),
    "SEPM20967": CLLocationCoordinate2D(latitude: 39.916785, longitude: -75.171373),
    "SEPM20024": CLLocationCoordinate2D(latitude: 39.915428, longitude: -75.358036),
    "SEPM20025": CLLocationCoordinate2D(latitude: 39.915276, longitude: -75.357953),
    "SEPM1917": CLLocationCoordinate2D(latitude: 39.968991, longitude: -75.274816),
    "SEPM1919": CLLocationCoordinate2D(latitude: 39.981006, longitude: -75.283986),
    "SEPM15329": CLLocationCoordinate2D(latitude: 39.928938, longitude: -75.292008),
    "SEPM30375": CLLocationCoordinate2D(latitude: 39.928653, longitude: -75.29202),
    "SEPM15366": CLLocationCoordinate2D(latitude: 39.914872, longitude: -75.369922),
    "SEPM15358": CLLocationCoordinate2D(latitude: 39.915024, longitude: -75.370004),
    "SEPM21014": CLLocationCoordinate2D(latitude: 39.972492, longitude: -75.177403),
    "SEPM21073": CLLocationCoordinate2D(latitude: 39.97244, longitude: -75.178171),
    "SEPM1946": CLLocationCoordinate2D(latitude: 39.916786, longitude: -75.380567),
    "SEPM1949": CLLocationCoordinate2D(latitude: 39.916626, longitude: -75.380614),
    "SEPM1280": CLLocationCoordinate2D(latitude: 39.957026, longitude: -75.162595),
    "SEPM1930": CLLocationCoordinate2D(latitude: 40.042079, longitude: -75.353617),
    "SEPM12196": CLLocationCoordinate2D(latitude: 39.983053, longitude: -75.101437),
    "SEPM21114": CLLocationCoordinate2D(latitude: 39.982875, longitude: -75.101544),
    "SEPM20981": CLLocationCoordinate2D(latitude: 39.979945, longitude: -75.107311),
    "SEPM21111": CLLocationCoordinate2D(latitude: 39.979758, longitude: -75.107536),
    "SEPM20982": CLLocationCoordinate2D(latitude: 39.979092, longitude: -75.108862),
    "SEPM21110": CLLocationCoordinate2D(latitude: 39.978914, longitude: -75.109052),
    "SEPM21113": CLLocationCoordinate2D(latitude: 39.981605, longitude: -75.104019),
    "SEPM20979": CLLocationCoordinate2D(latitude: 39.981783, longitude: -75.103782),
    "SEPM649": CLLocationCoordinate2D(latitude: 39.974153, longitude: -75.118181),
    "SEPM650": CLLocationCoordinate2D(latitude: 39.974331, longitude: -75.118038),
    "SEPM25779": CLLocationCoordinate2D(latitude: 39.973068, longitude: -75.119591),
    "SEPM21107": CLLocationCoordinate2D(latitude: 39.975441, longitude: -75.11573),
    "SEPM20984": CLLocationCoordinate2D(latitude: 39.975628, longitude: -75.115552),
    "SEPM21108": CLLocationCoordinate2D(latitude: 39.976729, longitude: -75.113302),
    "SEPM20983": CLLocationCoordinate2D(latitude: 39.976907, longitude: -75.113101),
    "SEPM21109": CLLocationCoordinate2D(latitude: 39.977981, longitude: -75.110887),
    "SEPM12218": CLLocationCoordinate2D(latitude: 39.978159, longitude: -75.110697),
    "SEPM341": CLLocationCoordinate2D(latitude: 39.984253, longitude: -75.099553),
    "SEPM1902": CLLocationCoordinate2D(latitude: 40.021401, longitude: -75.330287),
    "SEPM15355": CLLocationCoordinate2D(latitude: 39.928772, longitude: -75.333645),
    "SEPM15370": CLLocationCoordinate2D(latitude: 39.928665, longitude: -75.333515),
    "SEPM1953": CLLocationCoordinate2D(latitude: 39.940734, longitude: -75.325872),
    "SEPM30607": CLLocationCoordinate2D(latitude: 39.940752, longitude: -75.32612),
    "SEPM18602": CLLocationCoordinate2D(latitude: 39.948751, longitude: -75.299799),
    "SEPM18627": CLLocationCoordinate2D(latitude: 39.94859, longitude: -75.29987),
    "SEPM1286": CLLocationCoordinate2D(latitude: 39.924375, longitude: -75.169705),
    "SEPM797": CLLocationCoordinate2D(latitude: 39.991456, longitude: -75.122518),
    "SEPM2459": CLLocationCoordinate2D(latitude: 39.960542, longitude: -75.140402),
    "SEPM1944": CLLocationCoordinate2D(latitude: 39.918278, longitude: -75.348885),
    "SEPM1951": CLLocationCoordinate2D(latitude: 39.918011, longitude: -75.348992),
    "SEPM15330": CLLocationCoordinate2D(latitude: 39.927288, longitude: -75.292684),
    "SEPM30544": CLLocationCoordinate2D(latitude: 39.927288, longitude: -75.292519),
    "SEPM22129": CLLocationCoordinate2D(latitude: 39.951231, longitude: -75.19949),
    "SEPM22128": CLLocationCoordinate2D(latitude: 39.951385, longitude: -75.200871),
    "SEPM672": CLLocationCoordinate2D(latitude: 39.951647, longitude: -75.202795),
    "SEPM22147": CLLocationCoordinate2D(latitude: 39.952125, longitude: -75.205462),
    "SEPM22127": CLLocationCoordinate2D(latitude: 39.952027, longitude: -75.205687),
    "SEPM22151": CLLocationCoordinate2D(latitude: 39.952288, longitude: -75.206796),
    "SEPM1900": CLLocationCoordinate2D(latitude: 40.032677, longitude: -75.340765),
    "SEPM1276": CLLocationCoordinate2D(latitude: 39.987026, longitude: -75.156068),
    "SEPM1285": CLLocationCoordinate2D(latitude: 39.929809, longitude: -75.168522),
    "SEPM18621": CLLocationCoordinate2D(latitude: 39.921167, longitude: -75.345353),
    "SEPM18607": CLLocationCoordinate2D(latitude: 39.921159, longitude: -75.345542),
    "SEPM2463": CLLocationCoordinate2D(latitude: 40.000322, longitude: -75.106469),
    "SEPM1918": CLLocationCoordinate2D(latitude: 39.974795, longitude: -75.281577),
    "SEPM18613": CLLocationCoordinate2D(latitude: 39.918343, longitude: -75.391897),
    "SEPM18615": CLLocationCoordinate2D(latitude: 39.918209, longitude: -75.392145),
    "SEPM1929": CLLocationCoordinate2D(latitude: 40.034045, longitude: -75.344008),
    "SEPM18632": CLLocationCoordinate2D(latitude: 39.958921, longitude: -75.266263),
    "SEPM18597": CLLocationCoordinate2D(latitude: 39.958851, longitude: -75.2667),
    "SEPM1282": CLLocationCoordinate2D(latitude: 39.948734, longitude: -75.164415),
    "SEPM1943": CLLocationCoordinate2D(latitude: 39.924707, longitude: -75.339812),
    "SEPM1952": CLLocationCoordinate2D(latitude: 39.924617, longitude: -75.339659),
    "SEPM20729": CLLocationCoordinate2D(latitude: 39.946675, longitude: -75.207121),
    "SEPM20736": CLLocationCoordinate2D(latitude: 39.946987, longitude: -75.206907),
    "SEPM20737": CLLocationCoordinate2D(latitude: 39.945767, longitude: -75.20834),
    "SEPM20728": CLLocationCoordinate2D(latitude: 39.94541, longitude: -75.208565),
    "SEPM20739": CLLocationCoordinate2D(latitude: 39.944537, longitude: -75.209725),
    "SEPM20727": CLLocationCoordinate2D(latitude: 39.944323, longitude: -75.209797),
    "SEPM20958": CLLocationCoordinate2D(latitude: 39.943245, longitude: -75.210839),
    "SEPM20726": CLLocationCoordinate2D(latitude: 39.941953, longitude: -75.211728),
    "SEPM20740": CLLocationCoordinate2D(latitude: 39.942176, longitude: -75.211716),
    "SEPM297": CLLocationCoordinate2D(latitude: 39.940767, longitude: -75.212665),
    "SEPM302": CLLocationCoordinate2D(latitude: 39.940955, longitude: -75.212582),
    "SEPM20725": CLLocationCoordinate2D(latitude: 39.939886, longitude: -75.213907),
    "SEPM317": CLLocationCoordinate2D(latitude: 39.940064, longitude: -75.213848),
    "SEPM20724": CLLocationCoordinate2D(latitude: 39.938987, longitude: -75.215197),
    "SEPM20741": CLLocationCoordinate2D(latitude: 39.939192, longitude: -75.215102),
    "SEPM20723": CLLocationCoordinate2D(latitude: 39.938203, longitude: -75.216297),
    "SEPM20742": CLLocationCoordinate2D(latitude: 39.938408, longitude: -75.216214),
    "SEPM21208": CLLocationCoordinate2D(latitude: 39.937242, longitude: -75.217681),
    "SEPM20743": CLLocationCoordinate2D(latitude: 39.937438, longitude: -75.217598),
    "SEPM20744": CLLocationCoordinate2D(latitude: 39.936485, longitude: -75.218947),
    "SEPM20722": CLLocationCoordinate2D(latitude: 39.936262, longitude: -75.219054),
    "SEPM20721": CLLocationCoordinate2D(latitude: 39.935292, longitude: -75.22045),
    "SEPM20745": CLLocationCoordinate2D(latitude: 39.935524, longitude: -75.220308),
    "SEPM20720": CLLocationCoordinate2D(latitude: 39.934339, longitude: -75.22181),
    "SEPM20746": CLLocationCoordinate2D(latitude: 39.934553, longitude: -75.221703),
    "SEPM20747": CLLocationCoordinate2D(latitude: 39.933485, longitude: -75.223218),
    "SEPM20719": CLLocationCoordinate2D(latitude: 39.933297, longitude: -75.223289),
    "SEPM20718": CLLocationCoordinate2D(latitude: 39.932309, longitude: -75.224673),
    "SEPM20748": CLLocationCoordinate2D(latitude: 39.93263, longitude: -75.224448),
    "SEPM20716": CLLocationCoordinate2D(latitude: 39.930217, longitude: -75.227642),
    "SEPM20749": CLLocationCoordinate2D(latitude: 39.930457, longitude: -75.227535),
    "SEPM20717": CLLocationCoordinate2D(latitude: 39.929041, longitude: -75.229287),
    "SEPM20750": CLLocationCoordinate2D(latitude: 39.929282, longitude: -75.229191),
    "SEPM20715": CLLocationCoordinate2D(latitude: 39.928017, longitude: -75.230765),
    "SEPM303": CLLocationCoordinate2D(latitude: 39.928267, longitude: -75.230599),
    "SEPM20751": CLLocationCoordinate2D(latitude: 39.927519, longitude: -75.231675),
    "SEPM20714": CLLocationCoordinate2D(latitude: 39.927314, longitude: -75.231782),
    "SEPM20752": CLLocationCoordinate2D(latitude: 39.926557, longitude: -75.233047),
    "SEPM20713": CLLocationCoordinate2D(latitude: 39.926352, longitude: -75.233142),
    "SEPM20712": CLLocationCoordinate2D(latitude: 39.925479, longitude: -75.234396),
    "SEPM20753": CLLocationCoordinate2D(latitude: 39.925684, longitude: -75.234289),
    "SEPM20711": CLLocationCoordinate2D(latitude: 39.924615, longitude: -75.235614),
    "SEPM20754": CLLocationCoordinate2D(latitude: 39.924803, longitude: -75.235531),
    "SEPM20755": CLLocationCoordinate2D(latitude: 39.923886, longitude: -75.236856),
    "SEPM20710": CLLocationCoordinate2D(latitude: 39.923689, longitude: -75.236927),
    "SEPM20709": CLLocationCoordinate2D(latitude: 39.922621, longitude: -75.238441),
    "SEPM20756": CLLocationCoordinate2D(latitude: 39.922817, longitude: -75.23837),
    "SEPM20708": CLLocationCoordinate2D(latitude: 39.921463, longitude: -75.240097),
    "SEPM20757": CLLocationCoordinate2D(latitude: 39.921641, longitude: -75.240037),
    "SEPM20707": CLLocationCoordinate2D(latitude: 39.920483, longitude: -75.24148),
    "SEPM20758": CLLocationCoordinate2D(latitude: 39.920688, longitude: -75.241397),
    "SEPM20706": CLLocationCoordinate2D(latitude: 39.919361, longitude: -75.243077),
    "SEPM20759": CLLocationCoordinate2D(latitude: 39.919584, longitude: -75.242958),
    "SEPM20705": CLLocationCoordinate2D(latitude: 39.918432, longitude: -75.244412),
    "SEPM20760": CLLocationCoordinate2D(latitude: 39.918622, longitude: -75.244342),
    "SEPM304": CLLocationCoordinate2D(latitude: 39.917304, longitude: -75.246245),
    "SEPM20704": CLLocationCoordinate2D(latitude: 39.917099, longitude: -75.246376),
    "SEPM18844": CLLocationCoordinate2D(latitude: 39.921777, longitude: -75.288575),
    "SEPM12048": CLLocationCoordinate2D(latitude: 39.921643, longitude: -75.288705),
    "SEPM1921": CLLocationCoordinate2D(latitude: 39.993387, longitude: -75.298229),
    "SEPM1273": CLLocationCoordinate2D(latitude: 40.02456, longitude: -75.147856),
    "SEPM325": CLLocationCoordinate2D(latitude: 39.924685, longitude: -75.252447),
    "SEPM20774": CLLocationCoordinate2D(latitude: 39.924525, longitude: -75.252542),
    "SEPM2461": CLLocationCoordinate2D(latitude: 39.985526, longitude: -75.132013),
    ]
}
