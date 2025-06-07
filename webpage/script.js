class NYPScout {
    constructor() {
        this.currentScreen = 'departure-screen';
        this.selectedDestination = null;
        this.selectedDeparture = null;
        this.departureStationCode = null;
        this.highlightedIndex = -1;
        this.apiBaseUrl = '/api';
        this.updateInterval = null;
        this.currentTrainId = null;
        this.stations = [
            // NJ Transit stations (major ones)
            'New York Penn Station', 'Newark Penn Station', 'Secaucus', 'Woodbridge',
            'Metropark', 'New Brunswick', 'Princeton Junction', 'Trenton', 'Hamilton',
            'Morristown', 'Madison', 'Summit', 'Millburn', 'Short Hills', 'Newark Airport',
            'Elizabeth', 'Linden', 'Rahway', 'Metuchen', 'Edison', 'Iselin', 'Perth Amboy',
            'South Amboy', 'Aberdeen-Matawan', 'Hazlet', 'Red Bank', 'Little Silver', 'Monmouth Park',
            'Long Branch', 'Asbury Park', 'Bradley Beach', 'Belmar', 'Spring Lake', 'Manasquan',
            'Point Pleasant Beach', 'Bay Head', 'Montclair State University', 'Montclair Heights',
            'Upper Montclair', 'Mountain Avenue', 'Orange', 'East Orange', 'Brick Church',
            'Newark Broad Street', 'Bloomfield', 'Watsessing', 'Walnut Street', 'Glen Ridge',
            'Ridgewood', 'Ho-Ho-Kus', 'Waldwick', 'Allendale', 'Ramsey Route 17', 'Ramsey Main Street',
            'Mahwah', 'Suffern', 'Sloatsburg', 'Tuxedo', 'Harriman', 'Goshen', 'Campbell Hall',
            'Salisbury Mills-Cornwall', 'New Hampton', 'Middletown NJ', 'Otisville', 'Port Jervis',
            'Denville', 'Mount Tabor', 'Parsippany', 'Boonton', 'Mountain Lakes', 'Convent Station',
            'Madison', 'Chatham', 'Summit', 'New Providence', 'Murray Hill', 'Berkeley Heights',
            'Gillette', 'Stirling', 'Millington', 'Lyons', 'Basking Ridge', 'Bernardsville',
            'Far Hills', 'Peapack', 'Gladstone', 'Annandale', 'Lebanon', 'White House',
            'North Branch', 'Raritan', 'Somerville', 'Bound Brook', 'Dunellen', 'Plainfield',
            'Netherwood', 'Fanwood', 'Westfield', 'Garwood', 'Cranford', 'Roselle Park',
            'Union',
            
            // Amtrak stations (Northeast Corridor and beyond)
            'Boston South', 'Boston Back Bay', 'Providence', 'New Haven', 'Bridgeport',
            'Stamford', 'New Rochelle', 'Yonkers', 'Croton-Harmon', 'Poughkeepsie', 'Rhinecliff',
            'Hudson', 'Albany-Rensselaer', 'Schenectady', 'Amsterdam', 'Utica', 'Rome', 'Syracuse',
            'Rochester', 'Buffalo-Depew', 'Buffalo Exchange Street', 'Niagara Falls',
            'Philadelphia',
            'Wilmington', 'Aberdeen', 'BWI Airport', 'Baltimore Penn Station', 'New Carrollton',
            'Washington Union', 'Alexandria', 'Fredericksburg', 'Richmond Staples Mill',
            'Richmond Main Street', 'Petersburg', 'Rocky Mount', 'Wilson', 'Selma-Smithfield',
            'Raleigh', 'Cary', 'Southern Pines', 'Hamlet', 'Fayetteville', 'Dillon', 'Florence',
            'Kingstree', 'Charleston', 'Columbia', 'Camden', 'Denmark', 'Savannah', 'Jesup',
            'Jacksonville', 'Palatka', 'DeLand', 'Winter Park', 'Orlando', 'Kissimmee',
            'Lakeland', 'Tampa', 'Sebring', 'Okeechobee', 'West Palm Beach', 'Delray Beach',
            'Deerfield Beach', 'Fort Lauderdale', 'Hollywood', 'Hallandale Beach', 'Aventura',
            'Miami', 'Hialeah Market', 'Miami Airport', 'Toronto Union', 'Pittsburgh', 'New Orleans', 'Norfolk', 'Roanoke'

        ];

        // Station name to code mapping
        this.stationCodes = {
            // NJ Transit stations
            'New York Penn Station': 'NY',
            'Newark Penn Station': 'NP',
            'Secaucus': 'SE',
            'Woodbridge': 'WDB',
            'Metropark': 'MP',
            'New Brunswick': 'NB',
            'Princeton Junction': 'PJ',
            'Trenton': 'TR',
            'Trenton Transit Center': 'TR',
            'Hamilton': 'HL',
            'Morristown': 'MOR',
            'Madison': 'MAD',
            'Summit': 'ST',
            'Millburn': 'MB',
            'Short Hills': 'RT',
            'Newark Airport': 'NA',
            'Elizabeth': 'EZ',
            'Linden': 'LI',
            'Rahway': 'RH',
            'Metuchen': 'MU',
            'Edison': 'ED',
            'Iselin': 'ISE',
            'Perth Amboy': 'PAM',
            'South Amboy': 'SAM',
            'Aberdeen-Matawan': 'ABM',
            'Hazlet': 'HAZ',
            'Red Bank': 'RBK',
            'Little Silver': 'LIS',
            'Monmouth Park': 'MPK',
            'Long Branch': 'LBR',
            'Asbury Park': 'ASB',
            'Bradley Beach': 'BRB',
            'Belmar': 'BEL',
            'Spring Lake': 'SPL',
            'Manasquan': 'MAN',
            'Point Pleasant Beach': 'PPB',
            'Bay Head': 'BAY',
            'Montclair State University': 'MSU',
            'Montclair Heights': 'MCH',
            'Upper Montclair': 'UMC',
            'Mountain Avenue': 'MVA',
            'Orange': 'OG',
            'East Orange': 'EOR',
            'Brick Church': 'BU',
            'Newark Broad Street': 'ND',
            'Bloomfield': 'BLO',
            'Watsessing': 'WAT',
            'Walnut Street': 'WNS',
            'Glen Ridge': 'GLR',
            'Ridgewood': 'RID',
            'Ho-Ho-Kus': 'HHK',
            'Waldwick': 'WAL',
            'Allendale': 'ALL',
            'Ramsey Route 17': 'RR17',
            'Ramsey Main Street': 'RMS',
            'Mahwah': 'MAH',
            'Suffern': 'SUF',
            'Sloatsburg': 'SLO',
            'Tuxedo': 'TUX',
            'Harriman': 'HAR',
            'Goshen': 'GOS',
            'Campbell Hall': 'CAM',
            'Salisbury Mills-Cornwall': 'SMC',
            'New Hampton': 'NHA',
            'Middletown NJ': 'MTN',
            'Otisville': 'OTI',
            'Port Jervis': 'PJE',
            'Denville': 'DEN',
            'Mount Tabor': 'MTA',
            'Parsippany': 'PAR',
            'Boonton': 'BOO',
            'Mountain Lakes': 'MLA',
            'Convent Station': 'CON',
            'Chatham': 'CHA',
            'New Providence': 'NPR',
            'Murray Hill': 'MUR',
            'Berkeley Heights': 'BER',
            'Gillette': 'GIL',
            'Stirling': 'STI',
            'Millington': 'MIL2',
            'Lyons': 'LYO',
            'Basking Ridge': 'BAS',
            'Bernardsville': 'BER2',
            'Far Hills': 'FAR',
            'Peapack': 'PEA',
            'Gladstone': 'GLA',
            'Annandale': 'ANN',
            'Lebanon': 'LEB',
            'White House': 'WHI',
            'North Branch': 'NBR',
            'Raritan': 'RAR',
            'Somerville': 'SOM',
            'Bound Brook': 'BBK',
            'Dunellen': 'DUN',
            'Plainfield': 'PLA',
            'Netherwood': 'NET',
            'Fanwood': 'FAN',
            'Westfield': 'WES',
            'Garwood': 'GAR',
            'Cranford': 'CRA',
            'Roselle Park': 'ROP',
            'Union': 'US',

            // Amtrak stations
            'Boston South': 'BOS',
            'Boston Back Bay': 'BBY',
            'Providence': 'PVD',
            'New Haven': 'NHV',
            'Bridgeport': 'BRP',
            'Stamford': 'STM',
            'New Rochelle': 'NRO',
            'Yonkers': 'YNY',
            'Croton-Harmon': 'CRT',
            'Poughkeepsie': 'POU',
            'Rhinecliff': 'RHI',
            'Hudson': 'HUD',
            'Albany-Rensselaer': 'ALB',
            'Schenectady': 'SCH',
            'Amsterdam': 'AMS',
            'Utica': 'UTS',
            'Rome': 'ROM',
            'Syracuse': 'SYR',
            'Rochester': 'ROC',
            'Buffalo-Depew': 'BUF',
            'Buffalo Exchange Street': 'BFX',
            'Niagara Falls': 'NFL',
            'Philadelphia': 'PH',
            'Wilmington': 'WIL',
            'Aberdeen': 'ABE',
            'BWI Airport': 'BA',
            'Baltimore Penn Station': 'BL',
            'New Carrollton': 'NC',
            'Washington Union': 'WAS',
            'Alexandria': 'AXA',
            'Fredericksburg': 'FRB',
            'Richmond Staples Mill': 'RSM',
            'Richmond Main Street': 'RVM',
            'Petersburg': 'PTB',
            'Rocky Mount': 'RMT',
            'Wilson': 'WIL2',
            'Selma-Smithfield': 'SSM',
            'Raleigh': 'RAL',
            'Cary': 'CAR',
            'Southern Pines': 'SPN',
            'Hamlet': 'HAM2',
            'Fayetteville': 'FAY',
            'Dillon': 'DIL',
            'Florence': 'FLO',
            'Kingstree': 'KTR',
            'Charleston': 'CHS',
            'Columbia': 'COL',
            'Camden': 'CAM2',
            'Denmark': 'DEN2',
            'Savannah': 'SAV',
            'Jesup': 'JES',
            'Jacksonville': 'JAX',
            'Palatka': 'PAL',
            'DeLand': 'DEL',
            'Winter Park': 'WPK',
            'Orlando': 'ORL',
            'Kissimmee': 'KIS',
            'Lakeland': 'LAK',
            'Tampa': 'TPA',
            'Sebring': 'SEB',
            'Okeechobee': 'OKE',
            'West Palm Beach': 'WPB',
            'Delray Beach': 'DRB',
            'Deerfield Beach': 'DFB',
            'Fort Lauderdale': 'FTL',
            'Hollywood': 'HOL',
            'Hallandale Beach': 'HLB',
            'Aventura': 'AVE',
            'Miami': 'MIA',
            'Hialeah Market': 'HIA',
            'Miami Airport': 'MIP',
            'Toronto Union': 'TRTO',
            'Pittsburgh': 'PGH',
            'New Orleans': 'NOL',
            'Norfolk': 'NFK',
            'Roanoke': 'ROA'
        };
        this.initializeEventListeners();
        this.loadRecentDestinations();
    }

    getStationCode(stationName) {
        return this.stationCodes[stationName] || null;
    }

    getOriginDepartureTime(train) {
        // Find the stop that matches our departure station
        const originStop = train.stops?.find(stop => 
            this.getStationCode(stop.station_name) === this.departureStationCode
        );
        
        // Use the stop's departure time if found, otherwise fall back to train's overall time
        const timeToUse = originStop?.departure_time || train.departure_time;
        
        return this.formatTimeInEastern(timeToUse);
    }

    getOriginDepartureTimeValue(train) {
        // Find the stop that matches our departure station
        const originStop = train.stops?.find(stop => 
            this.getStationCode(stop.station_name) === this.departureStationCode
        );
        
        // Use the stop's departure time if found, otherwise fall back to train's overall time
        const timeToUse = originStop?.departure_time || train.departure_time;
        
        return new Date(timeToUse);
    }

    getEffectiveStatus(train) {
        // Use status_v2 when available, fallback to status for backward compatibility
        return train.status_v2 || train.status;
    }

    initializeEventListeners() {
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('option-btn') && !e.target.disabled) {
                this.handleOptionClick(e.target.dataset.action);
            }
            
            if (e.target.classList.contains('start-over-btn') || e.target.classList.contains('back-arrow-btn') || e.target.classList.contains('go-back-link')) {
                this.handleStartOver();
            }
            
            
            if (e.target.classList.contains('back-btn') || e.target.classList.contains('back-link')) {
                this.hideNewDestinationInput();
                this.navigateToScreen(e.target.dataset.back);
            }
            
            
            if (e.target.id === 'submit-train') {
                this.handleTrainSubmit();
            }
            
            if (e.target.classList.contains('autocomplete-item')) {
                this.selectDestination(e.target.textContent);
            }
            
            if (e.target.classList.contains('recent-item-text')) {
                this.selectDestination(e.target.textContent);
            }
            
            if (e.target.classList.contains('recent-item-remove')) {
                e.stopPropagation();
                const destination = e.target.closest('.recent-item').querySelector('.recent-item-text').textContent;
                this.removeRecentDestination(destination);
            }
            
            if (e.target.id === 'new-destination-btn') {
                this.showNewDestinationInput();
            }
            
            
            if (e.target.closest('.train-item')) {
                const trainItem = e.target.closest('.train-item');
                const trainId = trainItem.dataset.trainId;
                this.viewTrainDetails(trainId);
            }
            
            if (!e.target.closest('.autocomplete-container')) {
                this.hideAutocomplete();
            }
            
            // Close track popup when clicking outside
            if (!e.target.closest('.track-prediction-bar')) {
                document.querySelectorAll('.track-popup.show').forEach(popup => {
                    popup.classList.remove('show');
                });
            }
        });

        const destinationInput = document.getElementById('destination-input');
        if (destinationInput) {
            destinationInput.addEventListener('input', (e) => {
                this.handleDestinationInput(e.target.value);
            });
            
            destinationInput.addEventListener('keydown', (e) => {
                this.handleKeyNavigation(e);
            });
            
            destinationInput.addEventListener('focus', () => {
                if (destinationInput.value.length > 0) {
                    this.handleDestinationInput(destinationInput.value);
                }
            });
        }

        const trainInput = document.getElementById('train-number');
        if (trainInput) {
            trainInput.addEventListener('input', () => {
                this.validateTrainInput();
            });
            
            trainInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.handleTrainSubmit();
                }
            });
        }
    }

    handleOptionClick(action) {
        switch (action) {
            case 'depart-ny':
                this.selectedDeparture = 'New York Penn Station';
                this.departureStationCode = 'NY';
                this.navigateToScreen('main-screen');
                break;
            case 'depart-trenton':
                this.selectedDeparture = 'Trenton';
                this.departureStationCode = 'TR';
                this.navigateToScreen('main-screen');
                break;
            case 'depart-princeton':
                this.selectedDeparture = 'Princeton Junction';
                this.departureStationCode = 'PJ';
                this.navigateToScreen('main-screen');
                break;
            case 'depart-newark':
                this.selectedDeparture = 'Newark Penn Station';
                this.departureStationCode = 'NP';
                this.navigateToScreen('main-screen');
                break;
            case 'depart-metropark':
                this.selectedDeparture = 'Metropark';
                this.departureStationCode = 'MP';
                this.navigateToScreen('main-screen');
                break;
            case 'leaving-soon':
                this.navigateToScreen('leaving-soon-screen');
                break;
            case 'specific-train':
                this.navigateToScreen('train-input-screen');
                break;
            case 'food':
            case 'restrooms':
            case 'train-options':
                this.navigateToScreen('coming-soon-screen');
                break;
        }
    }

    navigateToScreen(screenId) {
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.add('hidden');
        });
        
        const targetScreen = document.getElementById(screenId);
        if (targetScreen) {
            targetScreen.classList.remove('hidden');
            this.currentScreen = screenId;
            
            if (screenId === 'train-input-screen') {
                setTimeout(() => {
                    document.getElementById('train-number').focus();
                }, 100);
            }
            
            // Stop updates when leaving train details screen
            if (screenId !== 'train-details-screen') {
                this.stopTrainUpdates();
            }
        }
    }

    validateTrainInput() {
        const input = document.getElementById('train-number');
        const submitBtn = document.getElementById('submit-train');
        const value = input.value.trim();
        
        if (value.length >= 2) {
            submitBtn.disabled = false;
        } else {
            submitBtn.disabled = true;
        }
    }

    handleDestinationInput(value) {
        const query = value.toLowerCase().trim();
        
        if (query.length === 0) {
            this.hideAutocomplete();
            return;
        }
        
        const matches = this.stations.filter(station => 
            station.toLowerCase().includes(query)
        ).slice(0, 8);
        
        this.showAutocomplete(matches);
    }
    
    showAutocomplete(matches) {
        const dropdown = document.getElementById('autocomplete-dropdown');
        
        if (matches.length === 0) {
            this.hideAutocomplete();
            return;
        }
        
        dropdown.innerHTML = matches.map(station => 
            `<div class="autocomplete-item">${station}</div>`
        ).join('');
        
        dropdown.style.display = 'block';
        this.highlightedIndex = -1;
    }
    
    hideAutocomplete() {
        const dropdown = document.getElementById('autocomplete-dropdown');
        dropdown.style.display = 'none';
        this.highlightedIndex = -1;
    }
    
    handleKeyNavigation(e) {
        const dropdown = document.getElementById('autocomplete-dropdown');
        const items = dropdown.querySelectorAll('.autocomplete-item');
        
        if (items.length === 0) return;
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.highlightedIndex = Math.min(this.highlightedIndex + 1, items.length - 1);
                this.updateHighlight(items);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.highlightedIndex = Math.max(this.highlightedIndex - 1, -1);
                this.updateHighlight(items);
                break;
            case 'Enter':
                e.preventDefault();
                if (this.highlightedIndex >= 0) {
                    this.selectDestination(items[this.highlightedIndex].textContent);
                }
                break;
            case 'Escape':
                this.hideAutocomplete();
                break;
        }
    }
    
    updateHighlight(items) {
        items.forEach((item, index) => {
            item.classList.toggle('highlighted', index === this.highlightedIndex);
        });
    }
    
    selectDestination(destination) {
        this.selectedDestination = destination;
        document.getElementById('destination-input').value = destination;
        this.hideAutocomplete();
        this.hideNewDestinationInput();
        this.saveRecentDestination(destination);
        
        // Set the destination title
        const destinationTitle = document.getElementById('destination-title');
        if (destinationTitle) {
            destinationTitle.textContent = `Trains to ${destination}`;
        }
        
        this.loadTrains(destination);
        this.navigateToScreen('leaving-soon-screen');
    }
    
    saveRecentDestination(destination) {
        let recent = JSON.parse(localStorage.getItem('nypscout-recent') || '[]');
        recent = recent.filter(item => item !== destination);
        recent.unshift(destination);
        recent = recent.slice(0, 5);
        localStorage.setItem('nypscout-recent', JSON.stringify(recent));
        this.loadRecentDestinations();
    }
    
    loadRecentDestinations() {
        const recent = JSON.parse(localStorage.getItem('nypscout-recent') || '[]');
        const container = document.getElementById('recent-destinations');
        const list = document.getElementById('recent-list');
        
        if (recent.length > 0) {
            const sortedRecent = [...recent].sort();
            list.innerHTML = sortedRecent.map(destination => 
                `<div class="recent-item">
                    <div class="recent-item-text">${destination}</div>
                    <button class="recent-item-remove">×</button>
                </div>`
            ).join('');
            container.style.display = 'block';
        } else {
            container.style.display = 'none';
        }
    }
    
    removeRecentDestination(destination) {
        let recent = JSON.parse(localStorage.getItem('nypscout-recent') || '[]');
        recent = recent.filter(item => item !== destination);
        localStorage.setItem('nypscout-recent', JSON.stringify(recent));
        this.loadRecentDestinations();
    }
    
    showNewDestinationInput() {
        const container = document.getElementById('autocomplete-container');
        const input = document.getElementById('destination-input');
        const btn = document.getElementById('new-destination-btn');
        
        container.style.display = 'block';
        btn.style.display = 'none';
        input.focus();
    }
    
    hideNewDestinationInput() {
        const container = document.getElementById('autocomplete-container');
        const input = document.getElementById('destination-input');
        const btn = document.getElementById('new-destination-btn');
        
        container.style.display = 'none';
        btn.style.display = 'inline-block';
        input.value = '';
        this.hideAutocomplete();
    }


    handleStartOver() {
        this.selectedDestination = null;
        this.selectedDeparture = null;
        this.departureStationCode = null;
        this.hideNewDestinationInput();
        this.stopTrainUpdates();
        this.navigateToScreen('departure-screen');
    }

    async viewTrainDetails(trainId) {
        this.currentTrainId = trainId;
        this.navigateToScreen('train-details-screen');
        await this.loadTrainDetailsById(trainId);
        this.startTrainUpdates();
    }

    startTrainUpdates() {
        // Clear any existing interval
        this.stopTrainUpdates();
        
        // Check for updates every 30 seconds
        this.updateInterval = setInterval(async () => {
            if (this.currentTrainId && this.currentScreen === 'train-details-screen') {
                await this.checkTrainUpdates();
            }
        }, 30000);
    }

    stopTrainUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    async checkTrainUpdates() {
        try {
            const currentTime = this.getEasternTimeISOString();
            let url = `${this.apiBaseUrl}/trains/?train_id=${encodeURIComponent(this.currentTrainId)}&departure_time_after=${currentTime}&consolidate=true&show_sources=true&include_predictions=true`;
            const response = await fetch(url);
            if (!response.ok) return;
            
            const data = await response.json();
            if (!data.trains || data.trains.length === 0) return;
            
            const updatedTrain = data.trains[0];
            
            // Check if status changed to BOARDING or track was assigned
            const wasBoarding = this.currentTrain && this.getEffectiveStatus(this.currentTrain) === 'BOARDING';
            const isNowBoarding = this.getEffectiveStatus(updatedTrain) === 'BOARDING';
            const trackChanged = this.currentTrain && this.currentTrain.track !== updatedTrain.track;
            
            // Update the stored train data
            this.currentTrain = updatedTrain;
            
            // If status changed to boarding or track changed, refresh the display
            if ((!wasBoarding && isNowBoarding) || trackChanged) {
                // Only update if we're still on the train details screen
                if (this.currentScreen === 'train-details-screen') {
                    this.displayTrainDetailsPage(updatedTrain);
                }
            }
        } catch (error) {
            // Silently fail - don't disrupt user experience with error messages
            console.log('Train update check failed:', error);
        }
    }

    getEasternTimeISOString() {
        const now = new Date();
        // Create a proper Eastern Time ISO string
        // The API expects Eastern Time formatted as ISO string
        const easternTimeString = now.toLocaleString("en-US", {
            timeZone: "America/New_York",
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
        
        // Convert MM/DD/YYYY, HH:mm:ss format to YYYY-MM-DDTHH:mm:ss
        const [datePart, timePart] = easternTimeString.split(', ');
        const [month, day, year] = datePart.split('/');
        return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T${timePart}`;
    }

    formatTimeInEastern(dateString) {
        const date = new Date(dateString);
        return date.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
            timeZone: 'America/New_York'
        });
    }

    formatDateTimeInEastern(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
            timeZone: 'America/New_York'
        });
    }

    async loadTrains(stationName) {
        try {
            const currentTime = this.getEasternTimeISOString();
            const fromStationCode = this.departureStationCode;
            const toStationCode = this.getStationCode(stationName);
            
            if (!fromStationCode) {
                throw new Error('Origin station code not available');
            }
            
            if (!toStationCode) {
                throw new Error('Destination station code not available');
            }
            
            const url = `${this.apiBaseUrl}/trains/?from_station_code=${fromStationCode}&to_station_code=${toStationCode}&departure_time_after=${currentTime}&limit=100&consolidate=true`;
            
            const response = await fetch(url);
            if (!response.ok) throw new Error('API request failed');
            const data = await response.json();
            this.displayTrains(data.trains);
        } catch (error) {
            this.displayErrorMessage('Unable to load train data');
        }
    }


    displayTrains(trains) {
        const trainsList = document.getElementById('trains-list');
        
        if (!trains || trains.length === 0) {
            trainsList.innerHTML = '<div class="no-trains">No trains found</div>';
            return;
        }

        // Deduplicate trains by train_id with priority system
        const deduplicatedTrains = Object.values(
            trains.reduce((acc, train) => {
                const existing = acc[train.train_id];
                
                if (!existing) {
                    acc[train.train_id] = train;
                    return acc;
                }
                
                // Calculate priority scores (higher is better)
                const getPriority = (t) => {
                    let score = 0;
                    
                    // Priority 1: Train originates from user's departure station
                    if (t.origin_station_code) {
                        if (t.origin_station_code === this.departureStationCode) {
                            score += 1000;
                        }
                    }
                    
                    // Priority 2: NJ Transit data over Amtrak data
                    if (t.data_source === 'njtransit') {
                        score += 100;
                    }
                    
                    // Priority 3: Use departure_time as tiebreaker (convert to timestamp)
                    const timestamp = new Date(t.departure_time).getTime() / 1000000000;
                    score += timestamp;
                    
                    return score;
                };
                
                const existingPriority = getPriority(existing);
                const currentPriority = getPriority(train);
                
                if (currentPriority > existingPriority) {
                    acc[train.train_id] = train;
                }
                
                return acc;
            }, {})
        );

        // Filter out trains departing more than 6 hours from now
        const now = new Date();
        const sixHoursFromNow = new Date(now.getTime() + 6 * 60 * 60 * 1000);
        
        const filteredTrains = deduplicatedTrains.filter(train => {
            const departureTime = this.getOriginDepartureTimeValue(train);
            return departureTime <= sixHoursFromNow;
        });
        
        // Sort trains by origin station departure time
        const sortedTrains = filteredTrains.sort((a, b) => {
            const timeA = this.getOriginDepartureTimeValue(a);
            const timeB = this.getOriginDepartureTimeValue(b);
            return timeA - timeB;
        });

        trainsList.innerHTML = sortedTrains.map(train => {
            const departureTime = this.getOriginDepartureTime(train);
            
            const effectiveStatus = this.getEffectiveStatus(train);
            const isBoarding = effectiveStatus === 'BOARDING';
            const statusClass = effectiveStatus === 'ON_TIME' ? 'on-time' : 
                               effectiveStatus === 'DELAYED' ? 'delayed' : 
                               effectiveStatus === 'DEPARTED' ? 'departed' : 
                               effectiveStatus === 'BOARDING' ? 'boarding' : 'scheduled';
            
            const statusText = effectiveStatus === 'ON_TIME' ? 'On Time' :
                              effectiveStatus === 'DELAYED' ? `Delayed ${train.delay_minutes || ''}min` :
                              effectiveStatus === 'DEPARTED' ? 'Departed' :
                              effectiveStatus === 'BOARDING' ? 'Boarding' :
                              '';

            // Build details array
            const details = [];
            
            if (isBoarding && train.track) {
                // For boarding trains with track, show "Boarding on Track X"
                details.push(`<span class="status ${statusClass}">Boarding on Track ${train.track}</span>`);
            } else {
                // For non-boarding trains, show track separately if assigned
                if (train.track && train.track !== 'TBD') {
                    details.push(`<span>Track ${train.track}</span>`);
                }
                
                // Show status if it's not empty or "Scheduled"
                if (statusText && statusText !== 'Scheduled') {
                    details.push(`<span class="status ${statusClass}">${statusText}</span>`);
                }
            }

            const detailsHtml = details.length > 0 ? `<div class="train-details">${details.join('')}</div>` : '';
            const boardingClass = isBoarding ? ' boarding' : '';
            const hasDetailsClass = details.length > 0 ? ' has-details' : '';

            // Get arrival time at the selected destination
            const arrivalTime = this.getDestinationArrivalTime(train);
            
            // Show destination if this is the "all trains" view
            const destinationText = this.selectedDestination ? '' : ` to ${train.destination}`;
            
            return `
                <div class="train-item${boardingClass}" data-train-id="${train.train_id}">
                    <div class="train-summary${hasDetailsClass}">Train ${train.train_id}${destinationText} from ${departureTime} to ${arrivalTime}</div>
                    ${detailsHtml}
                </div>
            `;
        }).join('');
    }

    displayErrorMessage(message) {
        const trainsList = document.getElementById('trains-list');
        trainsList.innerHTML = `<div class="error-message">${message}</div>`;
    }

    async loadTrainDetailsById(trainId) {
        try {
            console.log('Loading train details for ID:', trainId);
            const currentTime = this.getEasternTimeISOString();
            let url = `${this.apiBaseUrl}/trains/?train_id=${encodeURIComponent(trainId)}&departure_time_after=${currentTime}&consolidate=true&show_sources=true&include_predictions=true`;
            const response = await fetch(url);
            console.log('Response status:', response.status, response.statusText);
            if (!response.ok) {
                const errorText = await response.text();
                console.log('API error response:', errorText);
                throw new Error(`API request failed: ${response.status} ${response.statusText}`);
            }
            const data = await response.json();
            console.log('Train data received:', data);
            
            // Get the first train from the response (should be the matching train)
            if (data.trains && data.trains.length > 0) {
                this.displayTrainDetailsPage(data.trains[0]);
            } else {
                throw new Error('No train found with that ID');
            }
        } catch (error) {
            console.error('Error loading train details:', error);
            this.displayTrainDetailsError('Unable to load train details');
        }
    }

    displayTrainDetailsPage(train) {
        try {
            console.log('Displaying train details page for:', train);
            document.getElementById('train-title').textContent = `Train ${train.train_id} to ${train.destination}`;
            
            const basicInfo = document.getElementById('basic-info');
        const departureTime = train.departure_time ? this.formatDateTimeInEastern(train.departure_time) : '';
        
        const effectiveStatus = this.getEffectiveStatus(train);
        const statusText = effectiveStatus === 'ON_TIME' ? 'On Time' :
                          effectiveStatus === 'DELAYED' ? `Delayed ${train.delay_minutes || ''}min` :
                          effectiveStatus === 'DEPARTED' ? 'Departed' :
                          effectiveStatus || 'Scheduled';

        // Build the info items array
        const infoItems = [];
        
        // Only add departure time if it's valid
        if (departureTime) {
            infoItems.push(`<div class="info-item">
                <span class="value">${departureTime}</span>
            </div>`);
        }

        // Only show track field if not boarding
        const isBoarding = effectiveStatus === 'BOARDING';
        const hasAssignedTrack = train.track && train.track !== 'TBD';
        
        if (!isBoarding) {
            let trackContent;
            if (hasAssignedTrack) {
                trackContent = train.track;
            } else {
                // Use track predictions if available
                if (train.prediction_data && train.prediction_data.track_probabilities) {
                    trackContent = this.generateOwlTrackMessage(train.prediction_data.track_probabilities);
                } else {
                    trackContent = 'TBD';
                }
            }
            
            if (hasAssignedTrack) {
                infoItems.push(`<div class="info-item">
                    <span class="label">Track:</span>
                    <span class="value">${trackContent}</span>
                </div>`);
            } else {
                infoItems.push(`<div class="info-item">
                    <span class="value owl-message">${trackContent}</span>
                </div>`);
            }
        }


        // Add stops item
        const stopsContent = this.generateStopsDisplay(train.stops, train);
        infoItems.push(`<div class="info-item stops-item">
            <div class="stops-content">${stopsContent}</div>
        </div>`);


        basicInfo.innerHTML = infoItems.join('');

        // Add boarding class to info-section if boarding with assigned track
        const infoSection = document.querySelector('.info-section');
        const isBoardingWithTrack = isBoarding && hasAssignedTrack;
        if (isBoardingWithTrack) {
            infoSection.classList.add('boarding');
        } else {
            infoSection.classList.remove('boarding');
        }

        // Add boarding class to train title if boarding
        const trainTitle = document.getElementById('train-title');
        if (isBoarding) {
            trainTitle.classList.add('boarding-title');
        } else {
            trainTitle.classList.remove('boarding-title');
        }

        // Store prediction data for later use but don't display it yet
        this.currentTrainPrediction = train.prediction_data;
        
        // Store train data for later use
        this.currentTrain = train;
        
        // Station stops are now included in basicInfo above
        
        // Show the main train info section initially (reuse existing infoSection variable)
        infoSection.classList.remove('hidden');
        } catch (error) {
            console.error('Error in displayTrainDetailsPage:', error);
            this.displayTrainDetailsError('Unable to display train details');
        }
    }


    loadPredictionData() {
        const predictionInfo = document.getElementById('prediction-info');
        
        if (this.currentTrainPrediction && this.currentTrainPrediction.track_probabilities) {
            const topTracks = Object.entries(this.currentTrainPrediction.track_probabilities)
                .sort(([,a], [,b]) => b - a)
                .slice(0, 5);
            
            predictionInfo.innerHTML = `
                <div class="track-probabilities">
                    ${topTracks.map(([track, prob]) => `
                        <div class="track-prob">
                            <span class="track-number">Track ${track}</span>
                            <div class="prob-bar">
                                <div class="prob-fill" style="width: ${(prob * 100).toFixed(1)}%"></div>
                            </div>
                            <span class="prob-value">${(prob * 100).toFixed(1)}%</span>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            predictionInfo.innerHTML = '<div class="no-data">No prediction data available</div>';
        }
    }

    async loadStationStops(train) {
        // Station stops are now handled in displayTrainDetailsPage
        // This function is kept for compatibility but does nothing
    }
    



    generateStopsDisplay(stops, train = null) {
        if (!stops || stops.length === 0) {
            return '<div class="no-stops">No stops information available</div>';
        }

        // Find current position in journey
        const departedStops = stops.filter(stop => stop.departed === true);
        const currentStopIndex = departedStops.length;
        
        // Get the selected station (what the user is traveling to)
        const selectedStation = this.selectedDestination;
        
        // Find the index of the destination stop
        let destinationIndex = -1;
        if (selectedStation) {
            destinationIndex = stops.findIndex(stop => 
                stop.station_name.trim().toLowerCase() === selectedStation.trim().toLowerCase()
            );
        }
        
        // Only show stops up to and including the destination
        const stopsToShow = destinationIndex >= 0 ? stops.slice(0, destinationIndex + 1) : stops;

        return `<div class="stops-list">
            ${stopsToShow.map((stop, index) => {
                const scheduledTime = this.formatTimeInEastern(stop.scheduled_time);
                
                const departureTime = stop.departure_time !== stop.scheduled_time ? 
                    this.formatTimeInEastern(stop.departure_time) : null;

                const isDeparted = stop.departed === true;
                const isCurrent = index === currentStopIndex && !isDeparted;
                const isBoarding = stop.stop_status === 'BOARDING';
                // Highlight only the selected station (what the user is traveling to)
                const isDestination = selectedStation && 
                    stop.station_name.trim().toLowerCase() === selectedStation.trim().toLowerCase();
                
                let stopClass = 'stop-item';
                if (isDeparted) stopClass += ' departed';
                else if (isCurrent || isBoarding) stopClass += ' current';
                if (isDestination) stopClass += ' destination';
                
                let statusText = '';
                if (isBoarding) {
                    // Get the train data to access track information
                    const trackInfo = train && train.track && train.track !== 'TBD' 
                        ? ` on Track ${train.track}` 
                        : '';
                    statusText = `<span class="stop-status boarding">BOARDING${trackInfo}</span>`;
                } else if (isDeparted) {
                    statusText = '<span class="stop-status departed">DEPARTED</span>';
                }
                
                let timeDisplay = scheduledTime;
                if (departureTime && departureTime !== scheduledTime) {
                    timeDisplay = `<span class="scheduled-time">${scheduledTime}</span> → <span class="actual-time">${departureTime}</span>`;
                }

                return `
                    <div class="${stopClass}">
                        <div class="stop-indicator"></div>
                        <div class="stop-details">
                            <div class="stop-info">
                                <div class="stop-name">${stop.station_name}</div>
                                ${statusText}
                            </div>
                            <div class="stop-time">${timeDisplay}</div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>`;
    }

    getDestinationArrivalTime(train) {
        // Handle case where no stops data is available
        if (!train.stops || train.stops.length === 0) {
            return 'Not available';
        }

        // Find the stop for the station the user selected
        const selectedStation = this.selectedDestination;
        let targetStop = null;

        if (selectedStation) {
            // Try exact match first
            targetStop = train.stops.find(stop => 
                stop.station_name.trim().toLowerCase() === selectedStation.trim().toLowerCase()
            );
        }

        // If we can't find the selected station, fall back to last stop
        if (!targetStop) {
            targetStop = train.stops[train.stops.length - 1];
        }

        // Handle case where we still don't have a target stop
        if (!targetStop) {
            return 'Not available';
        }

        // Determine the best time to use for arrival
        let arrivalTime;
        if (targetStop.departure_time && 
            targetStop.departure_time !== targetStop.scheduled_time) {
            // Use actual departure time if it's different from scheduled (indicates delay/update)
            arrivalTime = targetStop.departure_time;
        } else {
            // Use scheduled time as fallback
            arrivalTime = targetStop.scheduled_time;
        }

        // Handle invalid time data
        if (!arrivalTime) {
            return 'Not available';
        }

        try {
            // Format the time using the same pattern as other times in the app
            return this.formatTimeInEastern(arrivalTime);
        } catch (error) {
            return 'Not available';
        }
    }

    generateOwlTrackMessage(trackProbabilities) {
        if (!trackProbabilities || Object.keys(trackProbabilities).length === 0) {
            return 'TBD';
        }

        const sortedTracks = Object.entries(trackProbabilities)
            .filter(([,prob]) => prob > 0.05)
            .sort(([,a], [,b]) => b - a);
        
        if (sortedTracks.length === 0) {
            return 'TBD';
        }
        
        const topTrack = sortedTracks[0];
        const topProb = topTrack[1];
        const fallbacks = sortedTracks.slice(1);
        
        // High confidence (≥80%)
        if (topProb >= 0.8) {
            let message = `Owl thinks it will be track ${topTrack[0]}`;
            if (fallbacks.length > 0) {
                const fallbackTracks = fallbacks.map(([track]) => track).join(', ');
                message += `, maybe ${fallbackTracks}`;
            }
            return message;
        }
        
        // Medium confidence (50-79%)
        if (topProb >= 0.5) {
            let message = `Owl thinks it may be track ${topTrack[0]}`;
            if (fallbacks.length > 0) {
                const fallbackTracks = fallbacks.map(([track]) => track).join(', ');
                message += `, possibly ${fallbackTracks}`;
            }
            return message;
        }
        
        // Multiple contenders (<50%)
        const topTracks = sortedTracks.slice(0, 5).map(([track]) => track);
        let message = `Owl guesses tracks ${topTracks.join(', ')}`;
        return message;
    }


    displayTrainDetailsError(message) {
        const trainTitle = document.getElementById('train-title');
        const basicInfo = document.getElementById('basic-info');
        
        if (trainTitle) trainTitle.textContent = 'Error Loading Train';
        if (basicInfo) basicInfo.innerHTML = `<div class="error-message">${message}</div>`;
    }

    async handleTrainSubmit() {
        const input = document.getElementById('train-number');
        const trainNumber = input.value.trim();
        
        if (trainNumber.length >= 2) {
            try {
                const currentTime = this.getEasternTimeISOString();
                let url = `${this.apiBaseUrl}/trains/?train_id=${encodeURIComponent(trainNumber)}&departure_time_after=${currentTime}&consolidate=true&show_sources=true&include_predictions=true`;
                const response = await fetch(url);
                if (!response.ok) throw new Error('Train not found');
                const data = await response.json();
                
                if (data.trains && data.trains.length > 0) {
                    this.viewTrainDetails(data.trains[0].train_id);
                } else {
                    throw new Error('Train not found');
                }
            } catch (error) {
                alert('Train not found');
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new NYPScout();
});
