import { Station } from '../types';

// Station data converted from iOS Stations.swift
export const STATIONS: Station[] = [
  // Major Hub Stations
  { code: 'NY', name: 'New York Penn Station', coordinates: { lat: 40.7506, lon: -73.9939 } },
  { code: 'NP', name: 'Newark Penn Station', coordinates: { lat: 40.7347, lon: -74.1644 } },
  { code: 'HB', name: 'Hoboken', coordinates: { lat: 40.734843, lon: -74.028043 } },
  { code: 'SE', name: 'Secaucus Upper Lvl', coordinates: { lat: 40.7612, lon: -74.0758 } },
  { code: 'TS', name: 'Secaucus Lower Lvl', coordinates: { lat: 40.7612, lon: -74.0758 } },
  { code: 'SC', name: 'Secaucus Concourse', coordinates: { lat: 40.7612, lon: -74.0758 } },
  { code: 'TR', name: 'Trenton', coordinates: { lat: 40.218518, lon: -74.753923 } },
  { code: 'PH', name: 'Philadelphia', coordinates: { lat: 39.9570, lon: -75.1820 } },

  // Northeast Corridor Line
  { code: 'PJ', name: 'Princeton Junction', coordinates: { lat: 40.3167, lon: -74.6233 } },
  { code: 'PR', name: 'Princeton' },
  { code: 'HL', name: 'Hamilton', coordinates: { lat: 40.2547, lon: -74.7036 } },
  { code: 'MP', name: 'Metropark', coordinates: { lat: 40.5378, lon: -74.3562 } },
  { code: 'NB', name: 'New Brunswick', coordinates: { lat: 40.4862, lon: -74.4518 } },
  { code: 'ED', name: 'Edison', coordinates: { lat: 40.5177, lon: -74.4075 } },
  { code: 'MU', name: 'Metuchen', coordinates: { lat: 40.5378, lon: -74.3562 } },
  { code: 'RH', name: 'Rahway', coordinates: { lat: 40.6039, lon: -74.2723 } },
  { code: 'LI', name: 'Linden', coordinates: { lat: 40.629487, lon: -74.251772 } },
  { code: 'EZ', name: 'Elizabeth', coordinates: { lat: 40.667859, lon: -74.215171 } },
  { code: 'NZ', name: 'North Elizabeth', coordinates: { lat: 40.680341475, lon: -74.2061729014 } },
  { code: 'NA', name: 'Newark Airport', coordinates: { lat: 40.7044941, lon: -74.1909959 } },
  { code: 'ND', name: 'Newark Broad Street', coordinates: { lat: 40.7418, lon: -74.1698 } },

  // North Jersey Coast Line
  { code: 'WB', name: 'Woodbridge', coordinates: { lat: 40.5559, lon: -74.2780 } },
  { code: 'PE', name: 'Perth Amboy', coordinates: { lat: 40.509372, lon: -74.27381259 } },
  { code: 'CH', name: 'South Amboy', coordinates: { lat: 40.48490168, lon: -74.2804993 } },
  { code: 'AM', name: 'Aberdeen-Matawan', coordinates: { lat: 40.419773943, lon: -74.22209923 } },
  { code: 'HZ', name: 'Hazlet', coordinates: { lat: 40.41515409, lon: -74.190629424 } },
  { code: 'MI', name: 'Middletown', coordinates: { lat: 40.39082051, lon: -74.116794 } },
  { code: 'RB', name: 'Red Bank', coordinates: { lat: 40.348271404, lon: -74.074151249 } },
  { code: 'LS', name: 'Little Silver', coordinates: { lat: 40.32654188, lon: -74.040546829 } },
  { code: 'MK', name: 'Monmouth Park', coordinates: { lat: 40.3086, lon: -74.0253 } },
  { code: 'LB', name: 'Long Branch', coordinates: { lat: 40.2970, lon: -73.9883 } },
  { code: 'EL', name: 'Elberon', coordinates: { lat: 40.265251, lon: -73.997479 } },
  { code: 'AH', name: 'Allenhurst', coordinates: { lat: 40.2301, lon: -74.0063 } },
  { code: 'AP', name: 'Asbury Park', coordinates: { lat: 40.2202, lon: -74.0120 } },
  { code: 'BB', name: 'Bradley Beach', coordinates: { lat: 40.1929, lon: -74.0218 } },
  { code: 'BS', name: 'Belmar', coordinates: { lat: 40.1784, lon: -74.0276 } },
  { code: 'LA', name: 'Spring Lake', coordinates: { lat: 40.1530, lon: -74.0340 } },
  { code: 'SQ', name: 'Manasquan', coordinates: { lat: 40.1057, lon: -74.0500 } },
  { code: 'PP', name: 'Point Pleasant Beach', coordinates: { lat: 40.0928885, lon: -74.048128 } },
  { code: 'BH', name: 'Bay Head', coordinates: { lat: 40.0771313, lon: -74.046189485 } },

  // Morris & Essex Lines
  { code: 'ST', name: 'Summit', coordinates: { lat: 40.716664548, lon: -74.3576803 } },
  { code: 'CM', name: 'Chatham', coordinates: { lat: 40.740191597, lon: -74.384824495 } },
  { code: 'MA', name: 'Madison', coordinates: { lat: 40.757040225, lon: -74.415224486 } },
  { code: 'CN', name: 'Convent Station', coordinates: { lat: 40.778934247, lon: -74.4433639138 } },
  { code: 'MR', name: 'Morristown', coordinates: { lat: 40.7971792932, lon: -74.474198069 } },
  { code: 'MX', name: 'Morris Plains', coordinates: { lat: 40.828603425, lon: -74.4782465138 } },
  { code: 'DV', name: 'Denville', coordinates: { lat: 40.8837, lon: -74.4753 } },
  { code: 'DO', name: 'Dover', coordinates: { lat: 40.88350334976419, lon: -74.55552377794903 } },
  { code: 'TB', name: 'Mount Tabor', coordinates: { lat: 40.875882396, lon: -74.481767307079 } },
  { code: 'HV', name: 'Mount Arlington', coordinates: { lat: 40.89659277960788, lon: -74.63275424450669 } },
  { code: 'HP', name: 'Lake Hopatcong', coordinates: { lat: 40.90408226231908, lon: -74.66561057518699 } },
  { code: 'NT', name: 'Netcong', coordinates: { lat: 40.897623899501745, lon: -74.70742034940882 } },
  { code: 'OL', name: 'Mount Olive', coordinates: { lat: 40.90739863717089, lon: -74.73084167518675 } },
  { code: 'HQ', name: 'Hackettstown', coordinates: { lat: 40.851897810525074, lon: -74.83489363939469 } },
  { code: 'MB', name: 'Millburn', coordinates: { lat: 40.7256749, lon: -74.3036915 } },
  { code: 'RT', name: 'Short Hills', coordinates: { lat: 40.725183794, lon: -74.323772644 } },
  { code: 'SO', name: 'South Orange', coordinates: { lat: 40.74598917, lon: -74.260345 } },
  { code: 'MW', name: 'Maplewood', coordinates: { lat: 40.731052531, lon: -74.275368 } },
  { code: 'OG', name: 'Orange', coordinates: { lat: 40.771899, lon: -74.2331103 } },
  { code: 'EO', name: 'East Orange', coordinates: { lat: 40.76089825, lon: -74.2107669 } },
  { code: 'BU', name: 'Brick Church', coordinates: { lat: 40.765656, lon: -74.21909888 } },
  { code: 'HI', name: 'Highland Avenue', coordinates: { lat: 40.7668668, lon: -74.24370939 } },
  { code: 'MV', name: 'Mountain View', coordinates: { lat: 40.913900511412734, lon: -74.26769562647546 } },

  // Gladstone Branch
  { code: 'MH', name: 'Murray Hill', coordinates: { lat: 40.69498340590801, lon: -74.40318790190945 } },
  { code: 'NV', name: 'New Providence', coordinates: { lat: 40.71207692699218, lon: -74.3865321865084 } },
  { code: 'BY', name: 'Berkeley Heights', coordinates: { lat: 40.68239885512966, lon: -74.44270357307379 } },
  { code: 'GI', name: 'Gillette', coordinates: { lat: 40.67823715581587, lon: -74.4682388381484 } },
  { code: 'SG', name: 'Stirling', coordinates: { lat: 40.67468000927561, lon: -74.49339662637885 } },
  { code: 'GO', name: 'Millington', coordinates: { lat: 40.67356917492084, lon: -74.52362581672504 } },
  { code: 'LY', name: 'Lyons', coordinates: { lat: 40.68483490714862, lon: -74.54952358841823 } },
  { code: 'BI', name: 'Basking Ridge', coordinates: { lat: 40.711327481896824, lon: -74.55527314719112 } },
  { code: 'BV', name: 'Bernardsville', coordinates: { lat: 40.716945533975355, lon: -74.57125871486349 } },
  { code: 'FH', name: 'Far Hills', coordinates: { lat: 40.685599814033345, lon: -74.6337807442374 } },
  { code: 'PC', name: 'Peapack', coordinates: { lat: 40.7052, lon: -74.6550 } },
  { code: 'GL', name: 'Gladstone', coordinates: { lat: 40.72024745131554, lon: -74.66637267519233 } },

  // Raritan Valley Line
  { code: 'US', name: 'Union', coordinates: { lat: 40.683542211, lon: -74.23800686 } },
  { code: 'RL', name: 'Roselle Park', coordinates: { lat: 40.6642, lon: -74.2687 } },
  { code: 'XC', name: 'Cranford', coordinates: { lat: 40.6559, lon: -74.3004 } },
  { code: 'GW', name: 'Garwood', coordinates: { lat: 40.65255335, lon: -74.325004422 } },
  { code: 'WF', name: 'Westfield', coordinates: { lat: 40.64944139, lon: -74.34758901 } },
  { code: 'FW', name: 'Fanwood', coordinates: { lat: 40.64061996, lon: -74.384423727 } },
  { code: 'NE', name: 'Netherwood', coordinates: { lat: 40.62921816688, lon: -74.403226634 } },
  { code: 'PF', name: 'Plainfield', coordinates: { lat: 40.6140, lon: -74.4147 } },
  { code: 'DN', name: 'Dunellen', coordinates: { lat: 40.5892, lon: -74.4719 } },
  { code: 'BK', name: 'Bound Brook', coordinates: { lat: 40.5612539, lon: -74.53021426 } },
  { code: 'BW', name: 'Bridgewater', coordinates: { lat: 40.561009, lon: -74.55175689 } },
  { code: 'SM', name: 'Somerville', coordinates: { lat: 40.56608, lon: -74.6138659 } },
  { code: 'RA', name: 'Raritan', coordinates: { lat: 40.57091522, lon: -74.6344244 } },
  { code: 'HG', name: 'High Bridge', coordinates: { lat: 40.666798999008535, lon: -74.89591082917332 } },
  { code: 'AN', name: 'Annandale', coordinates: { lat: 40.645122790094504, lon: -74.87893201752432 } },
  { code: 'ON', name: 'Lebanon', coordinates: { lat: 40.63685173471974, lon: -74.83598194792847 } },
  { code: 'WH', name: 'White House', coordinates: { lat: 40.615644648058776, lon: -74.77069208869021 } },
  { code: 'OR', name: 'North Branch', coordinates: { lat: 40.592500971292836, lon: -74.68422484941766 } },

  // Main/Bergen County Lines
  { code: 'KG', name: 'Kingsland', coordinates: { lat: 40.8123, lon: -74.1246 } },
  { code: 'LN', name: 'Lyndhurst', coordinates: { lat: 40.8123, lon: -74.1246 } },
  { code: 'DL', name: 'Delawanna', coordinates: { lat: 40.8318187, lon: -74.1314617 } },
  { code: 'PS', name: 'Passaic', coordinates: { lat: 40.8494377, lon: -74.133866768 } },
  { code: 'IF', name: 'Clifton', coordinates: { lat: 40.867912098, lon: -74.15326859 } },
  { code: 'RN', name: 'Paterson', coordinates: { lat: 40.9166, lon: -74.1710 } },
  { code: 'HW', name: 'Hawthorne', coordinates: { lat: 40.942528946, lon: -74.152399138 } },
  { code: 'RS', name: 'Glen Rock Main Line', coordinates: { lat: 40.9808, lon: -74.1168 } },
  { code: 'GK', name: 'Glen Rock Boro Hall', coordinates: { lat: 40.9595, lon: -74.1329 } },
  { code: 'RW', name: 'Ridgewood', coordinates: { lat: 40.9808, lon: -74.1168 } },
  { code: 'UF', name: 'Ho-Ho-Kus', coordinates: { lat: 40.9956, lon: -74.1115 } },
  { code: 'WK', name: 'Waldwick', coordinates: { lat: 41.0108, lon: -74.1267 } },
  { code: 'AZ', name: 'Allendale', coordinates: { lat: 41.0308516, lon: -74.13104499 } },
  { code: 'RY', name: 'Ramsey Main St', coordinates: { lat: 41.0571, lon: -74.1413 } },
  { code: '17', name: 'Ramsey Route 17', coordinates: { lat: 41.0615, lon: -74.1456 } },
  { code: 'MZ', name: 'Mahwah', coordinates: { lat: 41.0886, lon: -74.1438 } },
  { code: 'SF', name: 'Suffern', coordinates: { lat: 41.1144, lon: -74.1496 } },
  { code: 'BF', name: 'Fair Lawn-Broadway', coordinates: { lat: 40.9188, lon: -74.1316 } },
  { code: 'FZ', name: 'Radburn Fair Lawn', coordinates: { lat: 40.939645, lon: -74.12154647 } },
  { code: 'GD', name: 'Garfield', coordinates: { lat: 40.8815, lon: -74.1133 } },
  { code: 'PL', name: 'Plauderville', coordinates: { lat: 40.8879, lon: -74.1202 } },
  { code: 'RF', name: 'Rutherford', coordinates: { lat: 40.8267, lon: -74.1069 } },
  { code: 'WM', name: 'Wesmont', coordinates: { lat: 40.8356, lon: -74.0989 } },

  // Montclair-Boonton Line
  { code: 'BM', name: 'Bloomfield', coordinates: { lat: 40.792818916372745, lon: -74.19999693101497 } },
  { code: 'GG', name: 'Glen Ridge', coordinates: { lat: 40.800468228026226, lon: -74.20449363776208 } },
  { code: 'MC', name: 'Bay Street', coordinates: { lat: 40.808188091934255, lon: -74.20858344266387 } },
  { code: 'WA', name: 'Walnut Street', coordinates: { lat: 40.81716518884647, lon: -74.20955720561183 } },
  { code: 'HS', name: 'Montclair Heights', coordinates: { lat: 40.85778632525093, lon: -74.20258147801873 } },
  { code: 'UV', name: 'Montclair State U', coordinates: { lat: 40.869877328760076, lon: -74.1973970868374 } },
  { code: 'UM', name: 'Upper Montclair', coordinates: { lat: 40.8420714374858, lon: -74.20941682888828 } },
  { code: 'MS', name: 'Mountain Avenue', coordinates: { lat: 40.84886257848428, lon: -74.20572784233256 } },
  { code: 'WG', name: 'Watchung Avenue', coordinates: { lat: 40.82971140825341, lon: -74.20705692883614 } },
  { code: 'WT', name: 'Watsessing Avenue', coordinates: { lat: 40.78291485164349, lon: -74.1985652261131 } },
  { code: 'FA', name: 'Little Falls', coordinates: { lat: 40.880597100429924, lon: -74.23527448868244 } },
  { code: '23', name: 'Wayne-Route 23', coordinates: { lat: 40.90014887124657, lon: -74.25698821936236 } },
  { code: 'MT', name: 'Mountain Station', coordinates: { lat: 40.7553832255, lon: -74.2529918156 } },
  { code: 'BN', name: 'Boonton', coordinates: { lat: 40.90337853269087, lon: -74.4077830932363 } },
  { code: 'ML', name: 'Mountain Lakes', coordinates: { lat: 40.88593889355365, lon: -74.43361065984737 } },
  { code: 'LP', name: 'Lincoln Park', coordinates: { lat: 40.924111086002696, lon: -74.3018546214956 } },
  { code: 'TO', name: 'Towaco', coordinates: { lat: 40.9231266856343, lon: -74.34342958314522 } },
  { code: 'GA', name: 'Great Notch' },

  // Pascack Valley Line
  { code: 'WR', name: 'Wood Ridge', coordinates: { lat: 40.8449, lon: -74.0883 } },
  { code: 'TE', name: 'Teterboro', coordinates: { lat: 40.8602, lon: -74.0639 } },
  { code: 'EX', name: 'Essex Street', coordinates: { lat: 40.8836, lon: -74.0436 } },
  { code: 'AS', name: 'Anderson Street', coordinates: { lat: 40.8944, lon: -74.0447 } },
  { code: 'NH', name: 'New Bridge Landing', coordinates: { lat: 40.9079, lon: -74.0384 } },
  { code: 'RG', name: 'River Edge', coordinates: { lat: 40.9264, lon: -74.0413 } },
  { code: 'OD', name: 'Oradell', coordinates: { lat: 40.9545, lon: -74.0369 } },
  { code: 'EN', name: 'Emerson', coordinates: { lat: 40.9758, lon: -74.0281 } },
  { code: 'WW', name: 'Westwood', coordinates: { lat: 40.9909, lon: -74.0336 } },
  { code: 'HD', name: 'Hillsdale', coordinates: { lat: 41.00241888, lon: -74.040956 } },
  { code: 'WL', name: 'Woodcliff Lake', coordinates: { lat: 41.0230, lon: -74.0569 } },
  { code: 'PV', name: 'Park Ridge', coordinates: { lat: 41.0375, lon: -74.0406 } },
  { code: 'ZM', name: 'Montvale', coordinates: { lat: 41.0521, lon: -74.0372 } },
  { code: 'PQ', name: 'Pearl River', coordinates: { lat: 41.0595, lon: -74.0197 } },
  { code: 'NN', name: 'Nanuet', coordinates: { lat: 41.0869, lon: -74.0130 } },
  { code: 'SV', name: 'Spring Valley', coordinates: { lat: 41.1130, lon: -74.0436 } },

  // Port Jervis Line
  { code: 'XG', name: 'Sloatsburg', coordinates: { lat: 41.1568, lon: -74.1937 } },
  { code: 'TC', name: 'Tuxedo', coordinates: { lat: 41.1970, lon: -74.1885 } },
  { code: 'RM', name: 'Harriman', coordinates: { lat: 41.3098, lon: -74.1526 } },
  { code: 'CW', name: 'Salisbury Mills-Cornwall', coordinates: { lat: 41.436533265, lon: -74.101601729 } },
  { code: 'CB', name: 'Campbell Hall', coordinates: { lat: 41.4446, lon: -74.2452 } },
  { code: 'OS', name: 'Otisville', coordinates: { lat: 41.4783, lon: -74.5336 } },
  { code: 'PO', name: 'Port Jervis', coordinates: { lat: 41.3753, lon: -74.6897 } },

  // Additional NJ Transit Stations
  { code: 'AV', name: 'Avenel', coordinates: { lat: 40.5778386, lon: -74.2773454 } },
  { code: 'JA', name: 'Jersey Avenue', coordinates: { lat: 40.4769, lon: -74.4674 } },

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
