import { Station } from '../types';

// Station data converted from iOS Stations.swift
export const STATIONS: Station[] = [
  // Major Hub Stations
  { code: 'NY', name: 'New York Penn Station', coordinates: { lat: 40.750046, lon: -73.992358 } },
  { code: 'NP', name: 'Newark Penn Station', coordinates: { lat: 40.734221, lon: -74.164554 } },
  { code: 'HB', name: 'Hoboken', coordinates: { lat: 40.734843, lon: -74.028046 } },
  { code: 'SE', name: 'Secaucus Upper Lvl', coordinates: { lat: 40.761188, lon: -74.075821 } },
  { code: 'TS', name: 'Secaucus Lower Lvl', coordinates: { lat: 40.761188, lon: -74.075821 } },
  { code: 'SC', name: 'Secaucus Concourse', coordinates: { lat: 40.7612, lon: -74.0758 } },
  { code: 'TR', name: 'Trenton', coordinates: { lat: 40.218515, lon: -74.753926 } },
  { code: 'PH', name: 'Philadelphia', coordinates: { lat: 39.956565, lon: -75.182327 } },

  // Northeast Corridor Line
  { code: 'PJ', name: 'Princeton Junction', coordinates: { lat: 40.316316, lon: -74.623753 } },
  { code: 'PR', name: 'Princeton' },
  { code: 'HL', name: 'Hamilton', coordinates: { lat: 40.255309, lon: -74.70412 } },
  { code: 'MP', name: 'Metropark', coordinates: { lat: 40.56864, lon: -74.329394 } },
  { code: 'NB', name: 'New Brunswick', coordinates: { lat: 40.497278, lon: -74.445751 } },
  { code: 'ED', name: 'Edison', coordinates: { lat: 40.519148, lon: -74.410972 } },
  { code: 'MU', name: 'Metuchen', coordinates: { lat: 40.540736, lon: -74.360671 } },
  { code: 'RH', name: 'Rahway', coordinates: { lat: 40.606338, lon: -74.276692 } },
  { code: 'LI', name: 'Linden', coordinates: { lat: 40.629485, lon: -74.251772 } },
  { code: 'EZ', name: 'Elizabeth', coordinates: { lat: 40.667857, lon: -74.215174 } },
  { code: 'NZ', name: 'North Elizabeth', coordinates: { lat: 40.680265, lon: -74.206165 } },
  { code: 'NA', name: 'Newark Airport', coordinates: { lat: 40.704415, lon: -74.190717 } },
  { code: 'ND', name: 'Newark Broad Street', coordinates: { lat: 40.747621, lon: -74.171943 } },

  // North Jersey Coast Line
  { code: 'WB', name: 'Woodbridge', coordinates: { lat: 40.55661, lon: -74.277751 } },
  { code: 'PE', name: 'Perth Amboy', coordinates: { lat: 40.509398, lon: -74.273752 } },
  { code: 'CH', name: 'South Amboy', coordinates: { lat: 40.484308, lon: -74.28014 } },
  { code: 'AM', name: 'Aberdeen-Matawan', coordinates: { lat: 40.420161, lon: -74.223702 } },
  { code: 'HZ', name: 'Hazlet', coordinates: { lat: 40.415385, lon: -74.190393 } },
  { code: 'MI', name: 'Middletown', coordinates: { lat: 40.38978, lon: -74.116131 } },
  { code: 'RB', name: 'Red Bank', coordinates: { lat: 40.348284, lon: -74.074538 } },
  { code: 'LS', name: 'Little Silver', coordinates: { lat: 40.326715, lon: -74.041054 } },
  { code: 'MK', name: 'Monmouth Park', coordinates: { lat: 40.3086, lon: -74.0253 } },
  { code: 'LB', name: 'Long Branch', coordinates: { lat: 40.297145, lon: -73.988331 } },
  { code: 'EL', name: 'Elberon', coordinates: { lat: 40.265292, lon: -73.99762 } },
  { code: 'AH', name: 'Allenhurst', coordinates: { lat: 40.237659, lon: -74.006769 } },
  { code: 'AP', name: 'Asbury Park', coordinates: { lat: 40.215359, lon: -74.014786 } },
  { code: 'BB', name: 'Bradley Beach', coordinates: { lat: 40.203751, lon: -74.018891 } },
  { code: 'BS', name: 'Belmar', coordinates: { lat: 40.18059, lon: -74.027301 } },
  { code: 'LA', name: 'Spring Lake', coordinates: { lat: 40.150557, lon: -74.035481 } },
  { code: 'SQ', name: 'Manasquan', coordinates: { lat: 40.120573, lon: -74.047688 } },
  { code: 'PP', name: 'Point Pleasant Beach', coordinates: { lat: 40.092718, lon: -74.048191 } },
  { code: 'BH', name: 'Bay Head', coordinates: { lat: 40.077178, lon: -74.046183 } },

  // Morris & Essex Lines
  { code: 'ST', name: 'Summit', coordinates: { lat: 40.716549, lon: -74.357807 } },
  { code: 'CM', name: 'Chatham', coordinates: { lat: 40.740137, lon: -74.384812 } },
  { code: 'MA', name: 'Madison', coordinates: { lat: 40.757028, lon: -74.415105 } },
  { code: 'CN', name: 'Convent Station', coordinates: { lat: 40.779038, lon: -74.443435 } },
  { code: 'MR', name: 'Morristown', coordinates: { lat: 40.797113, lon: -74.474086 } },
  { code: 'MX', name: 'Morris Plains', coordinates: { lat: 40.828637, lon: -74.478197 } },
  { code: 'DV', name: 'Denville', coordinates: { lat: 40.8839, lon: -74.481513 } },
  { code: 'DO', name: 'Dover', coordinates: { lat: 40.883415, lon: -74.555887 } },
  { code: 'TB', name: 'Mount Tabor', coordinates: { lat: 40.875904, lon: -74.481915 } },
  { code: 'HV', name: 'Mount Arlington', coordinates: { lat: 40.89659, lon: -74.632731 } },
  { code: 'HP', name: 'Lake Hopatcong', coordinates: { lat: 40.904219, lon: -74.665697 } },
  { code: 'NT', name: 'Netcong', coordinates: { lat: 40.897552, lon: -74.707317 } },
  { code: 'OL', name: 'Mount Olive', coordinates: { lat: 40.907376, lon: -74.730653 } },
  { code: 'HQ', name: 'Hackettstown', coordinates: { lat: 40.851444, lon: -74.835352 } },
  { code: 'MB', name: 'Millburn', coordinates: { lat: 40.725622, lon: -74.303755 } },
  { code: 'RT', name: 'Short Hills', coordinates: { lat: 40.725249, lon: -74.323754 } },
  { code: 'SO', name: 'South Orange', coordinates: { lat: 40.745952, lon: -74.260538 } },
  { code: 'MW', name: 'Maplewood', coordinates: { lat: 40.731149, lon: -74.275427 } },
  { code: 'OG', name: 'Orange', coordinates: { lat: 40.771883, lon: -74.233103 } },
  { code: 'EO', name: 'East Orange', coordinates: { lat: 40.760977, lon: -74.210464 } },
  { code: 'BU', name: 'Brick Church', coordinates: { lat: 40.765134, lon: -74.218612 } },
  { code: 'HI', name: 'Highland Avenue', coordinates: { lat: 40.766863, lon: -74.243744 } },
  { code: 'MV', name: 'Mountain View', coordinates: { lat: 40.914402, lon: -74.268158 } },

  // Gladstone Branch
  { code: 'MH', name: 'Murray Hill', coordinates: { lat: 40.695068, lon: -74.403134 } },
  { code: 'NV', name: 'New Providence', coordinates: { lat: 40.712022, lon: -74.386501 } },
  { code: 'BY', name: 'Berkeley Heights', coordinates: { lat: 40.682345, lon: -74.442649 } },
  { code: 'GI', name: 'Gillette', coordinates: { lat: 40.678251, lon: -74.468317 } },
  { code: 'SG', name: 'Stirling', coordinates: { lat: 40.674579, lon: -74.493723 } },
  { code: 'GO', name: 'Millington', coordinates: { lat: 40.673513, lon: -74.523606 } },
  { code: 'LY', name: 'Lyons', coordinates: { lat: 40.684844, lon: -74.54947 } },
  { code: 'BI', name: 'Basking Ridge', coordinates: { lat: 40.711378, lon: -74.55527 } },
  { code: 'BV', name: 'Bernardsville', coordinates: { lat: 40.716845, lon: -74.571023 } },
  { code: 'FH', name: 'Far Hills', coordinates: { lat: 40.68571, lon: -74.633734 } },
  { code: 'PC', name: 'Peapack', coordinates: { lat: 40.708794, lon: -74.658469 } },
  { code: 'GL', name: 'Gladstone', coordinates: { lat: 40.720284, lon: -74.666371 } },

  // Raritan Valley Line
  { code: 'US', name: 'Union', coordinates: { lat: 40.683663, lon: -74.238605 } },
  { code: 'RL', name: 'Roselle Park', coordinates: { lat: 40.66715, lon: -74.266323 } },
  { code: 'XC', name: 'Cranford', coordinates: { lat: 40.655523, lon: -74.303226 } },
  { code: 'GW', name: 'Garwood', coordinates: { lat: 40.652569, lon: -74.324794 } },
  { code: 'WF', name: 'Westfield', coordinates: { lat: 40.649448, lon: -74.347629 } },
  { code: 'FW', name: 'Fanwood', coordinates: { lat: 40.64106, lon: -74.385003 } },
  { code: 'NE', name: 'Netherwood', coordinates: { lat: 40.629148, lon: -74.403455 } },
  { code: 'PF', name: 'Plainfield', coordinates: { lat: 40.618425, lon: -74.420163 } },
  { code: 'DN', name: 'Dunellen', coordinates: { lat: 40.590869, lon: -74.463043 } },
  { code: 'BK', name: 'Bound Brook', coordinates: { lat: 40.560929, lon: -74.530617 } },
  { code: 'BW', name: 'Bridgewater', coordinates: { lat: 40.559904, lon: -74.551741 } },
  { code: 'SM', name: 'Somerville', coordinates: { lat: 40.566075, lon: -74.61397 } },
  { code: 'RA', name: 'Raritan', coordinates: { lat: 40.571005, lon: -74.634364 } },
  { code: 'HG', name: 'High Bridge', coordinates: { lat: 40.666884, lon: -74.895863 } },
  { code: 'AN', name: 'Annandale', coordinates: { lat: 40.645173, lon: -74.878569 } },
  { code: 'ON', name: 'Lebanon', coordinates: { lat: 40.636903, lon: -74.835766 } },
  { code: 'WH', name: 'White House', coordinates: { lat: 40.615611, lon: -74.77066 } },
  { code: 'OR', name: 'North Branch', coordinates: { lat: 40.59202, lon: -74.683802 } },

  // Main/Bergen County Lines
  { code: 'KG', name: 'Kingsland', coordinates: { lat: 40.8123, lon: -74.1246 } },
  { code: 'LN', name: 'Lyndhurst', coordinates: { lat: 40.814165, lon: -74.122696 } },
  { code: 'DL', name: 'Delawanna', coordinates: { lat: 40.831369, lon: -74.131262 } },
  { code: 'PS', name: 'Passaic', coordinates: { lat: 40.849411, lon: -74.133933 } },
  { code: 'IF', name: 'Clifton', coordinates: { lat: 40.867998, lon: -74.153206 } },
  { code: 'RN', name: 'Paterson', coordinates: { lat: 40.914887, lon: -74.16733 } },
  { code: 'HW', name: 'Hawthorne', coordinates: { lat: 40.942539, lon: -74.152411 } },
  { code: 'RS', name: 'Glen Rock Main Line', coordinates: { lat: 40.962206, lon: -74.133485 } },
  { code: 'GK', name: 'Glen Rock Boro Hall', coordinates: { lat: 40.96137, lon: -74.1293 } },
  { code: 'RW', name: 'Ridgewood', coordinates: { lat: 40.980629, lon: -74.120592 } },
  { code: 'UF', name: 'Ho-Ho-Kus', coordinates: { lat: 40.997369, lon: -74.113521 } },
  { code: 'WK', name: 'Waldwick', coordinates: { lat: 41.012734, lon: -74.123412 } },
  { code: 'AZ', name: 'Allendale', coordinates: { lat: 41.030902, lon: -74.130957 } },
  { code: 'RY', name: 'Ramsey Main St', coordinates: { lat: 41.0571, lon: -74.1413 } },
  { code: '17', name: 'Ramsey Route 17', coordinates: { lat: 41.07513, lon: -74.145485 } },
  { code: 'MZ', name: 'Mahwah', coordinates: { lat: 41.094416, lon: -74.14662 } },
  { code: 'SF', name: 'Suffern', coordinates: { lat: 41.11354, lon: -74.153442 } },
  { code: 'BF', name: 'Fair Lawn-Broadway', coordinates: { lat: 40.922505, lon: -74.115236 } },
  { code: 'FZ', name: 'Radburn Fair Lawn', coordinates: { lat: 40.939914, lon: -74.121617 } },
  { code: 'GD', name: 'Garfield', coordinates: { lat: 40.866669, lon: -74.10556 } },
  { code: 'PL', name: 'Plauderville', coordinates: { lat: 40.884916, lon: -74.102695 } },
  { code: 'RF', name: 'Rutherford', coordinates: { lat: 40.828248, lon: -74.100563 } },
  { code: 'WM', name: 'Wesmont', coordinates: { lat: 40.854979, lon: -74.096951 } },

  // Montclair-Boonton Line
  { code: 'BM', name: 'Bloomfield', coordinates: { lat: 40.792709, lon: -74.200043 } },
  { code: 'GG', name: 'Glen Ridge', coordinates: { lat: 40.80059, lon: -74.204655 } },
  { code: 'MC', name: 'Bay Street', coordinates: { lat: 40.808178, lon: -74.208681 } },
  { code: 'WA', name: 'Walnut Street', coordinates: { lat: 40.81716518884647, lon: -74.20955720561183 } },
  { code: 'HS', name: 'Montclair Heights', coordinates: { lat: 40.857536, lon: -74.2025 } },
  { code: 'UV', name: 'Montclair State U', coordinates: { lat: 40.869782, lon: -74.197439 } },
  { code: 'UM', name: 'Upper Montclair', coordinates: { lat: 40.842004, lon: -74.209368 } },
  { code: 'MS', name: 'Mountain Avenue', coordinates: { lat: 40.848715, lon: -74.205306 } },
  { code: 'WG', name: 'Watchung Avenue', coordinates: { lat: 40.829514, lon: -74.206934 } },
  { code: 'WT', name: 'Watsessing Avenue', coordinates: { lat: 40.782743, lon: -74.198451 } },
  { code: 'FA', name: 'Little Falls', coordinates: { lat: 40.880669, lon: -74.235372 } },
  { code: '23', name: 'Wayne-Route 23', coordinates: { lat: 40.900254, lon: -74.256971 } },
  { code: 'MT', name: 'Mountain Station', coordinates: { lat: 40.755365, lon: -74.253024 } },
  { code: 'BN', name: 'Boonton', coordinates: { lat: 40.903378, lon: -74.407736 } },
  { code: 'ML', name: 'Mountain Lakes', coordinates: { lat: 40.885947, lon: -74.433604 } },
  { code: 'LP', name: 'Lincoln Park', coordinates: { lat: 40.924138, lon: -74.301826 } },
  { code: 'TO', name: 'Towaco', coordinates: { lat: 40.922809, lon: -74.343842 } },
  { code: 'GA', name: 'Great Notch' },

  // Pascack Valley Line
  { code: 'WR', name: 'Wood Ridge', coordinates: { lat: 40.843974, lon: -74.078719 } },
  { code: 'TE', name: 'Teterboro', coordinates: { lat: 40.864858, lon: -74.062676 } },
  { code: 'EX', name: 'Essex Street', coordinates: { lat: 40.878973, lon: -74.051893 } },
  { code: 'AS', name: 'Anderson Street', coordinates: { lat: 40.894458, lon: -74.043781 } },
  { code: 'NH', name: 'New Bridge Landing', coordinates: { lat: 40.910856, lon: -74.035044 } },
  { code: 'RG', name: 'River Edge', coordinates: { lat: 40.935146, lon: -74.02914 } },
  { code: 'OD', name: 'Oradell', coordinates: { lat: 40.953478, lon: -74.029983 } },
  { code: 'EN', name: 'Emerson', coordinates: { lat: 40.975036, lon: -74.027474 } },
  { code: 'WW', name: 'Westwood', coordinates: { lat: 40.990817, lon: -74.032696 } },
  { code: 'HD', name: 'Hillsdale', coordinates: { lat: 41.002414, lon: -74.041033 } },
  { code: 'WL', name: 'Woodcliff Lake', coordinates: { lat: 41.021078, lon: -74.040775 } },
  { code: 'PV', name: 'Park Ridge', coordinates: { lat: 41.032305, lon: -74.036164 } },
  { code: 'ZM', name: 'Montvale', coordinates: { lat: 41.040879, lon: -74.029152 } },
  { code: 'PQ', name: 'Pearl River', coordinates: { lat: 41.058181, lon: -74.02232 } },
  { code: 'NN', name: 'Nanuet', coordinates: { lat: 41.090015, lon: -74.014794 } },
  { code: 'SV', name: 'Spring Valley', coordinates: { lat: 41.111978, lon: -74.043991 } },

  // Port Jervis Line
  { code: 'XG', name: 'Sloatsburg', coordinates: { lat: 41.157138, lon: -74.191307 } },
  { code: 'TC', name: 'Tuxedo', coordinates: { lat: 41.194208, lon: -74.18446 } },
  { code: 'RM', name: 'Harriman', coordinates: { lat: 41.293354, lon: -74.13987 } },
  { code: 'CW', name: 'Salisbury Mills-Cornwall', coordinates: { lat: 41.437073, lon: -74.101871 } },
  { code: 'CB', name: 'Campbell Hall', coordinates: { lat: 41.450917, lon: -74.266554 } },
  { code: 'OS', name: 'Otisville', coordinates: { lat: 41.471784, lon: -74.529212 } },
  { code: 'PO', name: 'Port Jervis', coordinates: { lat: 41.374899, lon: -74.694622 } },

  // Additional NJ Transit Stations
  { code: 'AV', name: 'Avenel', coordinates: { lat: 40.57762, lon: -74.27753 } },
  { code: 'JA', name: 'Jersey Avenue', coordinates: { lat: 40.476912, lon: -74.467363 } },

  // Pennsylvania Stations (Keystone Service)
  { code: 'MIDPA', name: 'Middletown PA' },
  { code: 'ELT', name: 'Elizabethtown' },
  { code: 'MJY', name: 'Mount Joy' },
  { code: 'PKB', name: 'Parkesburg' },
  { code: 'COT', name: 'Coatesville' },
  { code: 'DOW', name: 'Downingtown' },
  { code: 'EXT', name: 'Exton' },
  { code: 'PAO', name: 'Paoli' },

  // Amtrak Northeast Corridor
  { code: 'BOS', name: 'Boston South', coordinates: { lat: 42.3520, lon: -71.0552 } },
  { code: 'BBY', name: 'Boston Back Bay', coordinates: { lat: 42.3473, lon: -71.0764 } },
  { code: 'PVD', name: 'Providence', coordinates: { lat: 41.8256, lon: -71.4160 } },
  { code: 'KIN', name: 'Kingston', coordinates: { lat: 41.4885, lon: -71.5204 } },
  { code: 'WLY', name: 'Westerly', coordinates: { lat: 41.3770, lon: -71.8307 } },
  { code: 'NLC', name: 'New London', coordinates: { lat: 41.3543, lon: -72.0939 } },
  { code: 'OSB', name: 'Old Saybrook', coordinates: { lat: 41.3005, lon: -72.3760 } },
  { code: 'NHV', name: 'New Haven', coordinates: { lat: 41.2987, lon: -72.9259 } },
  { code: 'BRP', name: 'Bridgeport', coordinates: { lat: 41.1767, lon: -73.1874 } },
  { code: 'STM', name: 'Stamford', coordinates: { lat: 41.0462, lon: -73.5427 } },
  { code: 'BL', name: 'Baltimore Station', coordinates: { lat: 39.3081, lon: -76.6175 } },
  { code: 'BA', name: 'BWI Thurgood Marshall Airport', coordinates: { lat: 39.1896, lon: -76.6934 } },
  { code: 'WS', name: 'Washington Union Station', coordinates: { lat: 38.8973, lon: -77.0064 } },
  { code: 'WI', name: 'Wilmington Station', coordinates: { lat: 39.7369, lon: -75.5522 } },

  // Additional Amtrak Stations
  { code: 'HFD', name: 'Hartford', coordinates: { lat: 41.7678, lon: -72.6821 } },
  { code: 'MDN', name: 'Meriden', coordinates: { lat: 41.5390, lon: -72.8012 } },
  { code: 'WFD', name: 'Wallingford', coordinates: { lat: 41.4571, lon: -72.8254 } },
  { code: 'WNL', name: 'Windsor Locks', coordinates: { lat: 41.9272, lon: -72.6286 } },
  { code: 'SPG', name: 'Springfield', coordinates: { lat: 42.1060, lon: -72.5936 } },
  { code: 'CLA', name: 'Claremont', coordinates: { lat: 43.3688, lon: -72.3793 } },
  { code: 'DOV', name: 'Dover NH', coordinates: { lat: 43.1979, lon: -70.8737 } },
  { code: 'DHM', name: 'Durham-UNH', coordinates: { lat: 43.1340, lon: -70.9267 } },
  { code: 'EXR', name: 'Exeter', coordinates: { lat: 42.9809, lon: -70.9478 } },
  { code: 'NCR', name: 'New Carrollton', coordinates: { lat: 38.9533, lon: -76.8644 } },
  { code: 'ABE', name: 'Aberdeen', coordinates: { lat: 39.5095, lon: -76.1630 } },
  { code: 'ALX', name: 'Alexandria', coordinates: { lat: 38.8062, lon: -77.0626 } },
  { code: 'CVS', name: 'Charlottesville', coordinates: { lat: 38.0320, lon: -78.4921 } },
  { code: 'LOR', name: 'Lorton', coordinates: { lat: 38.7060, lon: -77.2214 } },
  { code: 'NFK', name: 'Norfolk', coordinates: { lat: 36.8583, lon: -76.2876 } },
  { code: 'RVM', name: 'Richmond Main Street', coordinates: { lat: 37.6143, lon: -77.4966 } },
  { code: 'RVR', name: 'Richmond Staples Mill Road', coordinates: { lat: 37.61741, lon: -77.49755 } },
  { code: 'RNK', name: 'Roanoke', coordinates: { lat: 37.3077, lon: -79.9803 } },
  { code: 'HAR', name: 'Harrisburg', coordinates: { lat: 40.2616, lon: -76.8782 } },
  { code: 'LNC', name: 'Lancaster', coordinates: { lat: 40.0538, lon: -76.3076 } },

  // Southeast Amtrak Stations (Silver Star/Meteor and Carolinian/Piedmont routes)
  { code: 'CLT', name: 'Charlotte', coordinates: { lat: 35.2411460876465, lon: -80.8236389160156 } },
  { code: 'RGH', name: 'Raleigh', coordinates: { lat: 35.7795, lon: -78.6382 } },
  { code: 'GRB', name: 'Greensboro' },
  { code: 'DNC', name: 'Durham', coordinates: { lat: 35.9970359802246, lon: -78.9072265625 } },
  { code: 'RMT', name: 'Rocky Mount', coordinates: { lat: 35.9382, lon: -77.7905 } },
  { code: 'WLN', name: 'Wilson', coordinates: { lat: 35.7230682373047, lon: -77.9082946777344 } },
  { code: 'CAR', name: 'Cary' },
  { code: 'SOU', name: 'Southern Pines' },
  { code: 'HPT', name: 'High Point', coordinates: { lat: 35.9575080871582, lon: -80.0058364868164 } },
  { code: 'SAL', name: 'Salisbury', coordinates: { lat: 35.6740, lon: -80.4842 } },
  { code: 'GAS', name: 'Gastonia', coordinates: { lat: 35.2683563232422, lon: -81.1639785766602 } },
  { code: 'HAM', name: 'Hamlet', coordinates: { lat: 34.8830718994141, lon: -79.6984558105469 } },
  { code: 'SEL', name: 'Selma-Smithfield' },
  { code: 'PTB', name: 'Petersburg', coordinates: { lat: 37.2416191101074, lon: -77.4289703369141 } },
  { code: 'CHS', name: 'Charleston', coordinates: { lat: 32.8755340576172, lon: -79.9989013671875 } },
  { code: 'SPB', name: 'Spartanburg', coordinates: { lat: 34.9496, lon: -81.9318 } },
  { code: 'GVL', name: 'Greenville' },
  { code: 'KTR', name: 'Kingstree', coordinates: { lat: 33.664379119873, lon: -79.8290634155273 } },
  { code: 'FLO', name: 'Florence', coordinates: { lat: 34.1988182067871, lon: -79.7570953369141 } },
  { code: 'DIL', name: 'Dillon', coordinates: { lat: 34.418285369873, lon: -79.3717575073242 } },
  { code: 'CSN', name: 'Clemson', coordinates: { lat: 34.6910, lon: -82.8325 } },
  { code: 'SAV', name: 'Savannah', coordinates: { lat: 32.0835, lon: -81.0998 } },
  { code: 'ATL', name: 'Atlanta', coordinates: { lat: 33.7995643615723, lon: -84.3917846679688 } },
  { code: 'JES', name: 'Jesup' },
  { code: 'GAI', name: 'Gainesville GA' },
  { code: 'TOC', name: 'Toccoa' },
  { code: 'JAX', name: 'Jacksonville', coordinates: { lat: 30.3665771484375, lon: -81.7246017456055 } },
  { code: 'MIA', name: 'Miami', coordinates: { lat: 25.8498477935791, lon: -80.2580718994141 } },
  { code: 'ORL', name: 'Orlando', coordinates: { lat: 28.5256938934326, lon: -81.3817443847656 } },
  { code: 'TPA', name: 'Tampa', coordinates: { lat: 27.9506, lon: -82.4572 } },
  { code: 'FTL', name: 'Fort Lauderdale', coordinates: { lat: 26.1196136474609, lon: -80.1701889038086 } },
  { code: 'WPB', name: 'West Palm Beach', coordinates: { lat: 26.7153, lon: -80.0534 } },
  { code: 'KIS', name: 'Kissimmee', coordinates: { lat: 28.293270111084, lon: -81.4048690795898 } },
  { code: 'LKL', name: 'Lakeland', coordinates: { lat: 28.04568, lon: -81.95188 } },
  { code: 'WPK', name: 'Winter Park FL', coordinates: { lat: 28.5990, lon: -81.3392 } },
  { code: 'DLD', name: 'DeLand', coordinates: { lat: 29.0168342590332, lon: -81.3524551391602 } },
  { code: 'SAN', name: 'Sanford FL' },
  { code: 'HLW', name: 'Hollywood FL' },
  { code: 'DLB', name: 'Delray Beach', coordinates: { lat: 26.4551792144775, lon: -80.092529296875 } },
  { code: 'WLD', name: 'Waldo' },
  { code: 'OCA', name: 'Ocala' },
  { code: 'WTH', name: 'Winter Haven', coordinates: { lat: 28.0222, lon: -81.7323 } },
  { code: 'PAL', name: 'Palatka' },
  { code: 'THU', name: 'Thurmond' },
].sort((a, b) => a.name.localeCompare(b.name));

// Primary departure stations
export const DEPARTURE_STATIONS = [
  'NY', 'HB', 'MP', 'PJ', 'HL', 'TR', 'LB', 'PF', 'DN', 'RA',
  'PH', 'WI', 'BL', 'WS', 'RVR', 'CLT', 'RGH', 'SAV', 'JAX',
  'ORL', 'TPA', 'MIA', 'ATL'
];

// Helper functions
export function getStationByCode(code: string): Station | undefined {
  return STATIONS.find(s => s.code === code);
}

export function getStationByName(name: string): Station | undefined {
  return STATIONS.find(s => s.name === name);
}

export function searchStations(query: string): Station[] {
  if (!query) return [];
  const q = query.toLowerCase();
  return STATIONS
    .filter(s =>
      s.name.toLowerCase().includes(q) ||
      s.code.toLowerCase().includes(q)
    )
    .slice(0, 10);
}

export function getPrimaryDepartureStations(): Station[] {
  return DEPARTURE_STATIONS
    .map(code => getStationByCode(code))
    .filter((s): s is Station => s !== undefined);
}
