import React from 'react';
import { connect } from 'react-redux'
import {APP} from '../Config.jsx'
import {ui_config} from '../Config.jsx'
import {Disco} from '../disco/disco.jsx'

class DefaultHome extends React.Component {

    render(){
        return [ <header>
                    <div className="jumbotron jumbotron-fluid bg-info text-white text-center">
                        <div className="container">
                            <h1 className="display-4">jsonapi-admin UI</h1>
                            React+redux js frontend for a jsonapi backend
                        </div>
                    </div>
                </header>,
                <div className="container">
                    <ul>
                        <li>This framework implements CRUD operations on the jsonapi at <a href={this.props.url}>{this.props.url}</a> </li>
                        
                        <li>UI Configuration <Disco api_root={this.props.url}/>
                            <pre>{JSON.stringify(APP,null,2)}</pre>
                        </li>
                    </ul>
                </div> ]
                
    }
}


class Home extends React.Component {

    render(){
        let home = ui_config.home ? ui_config.home : <DefaultHome url={this.props.inputflag.url} />
        return (
            <div>
                {home}
            </div>
        );
    }
};

const mapStateToProps = state => ({
    inputflag: state.inputReducer
})

let exported = Home

export default connect(mapStateToProps)(exported);
